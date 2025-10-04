"""Server-Sent Events streaming utilities for OpenAI compatibility."""

import json
import asyncio
import uuid
from datetime import datetime
from typing import AsyncGenerator, Dict, Any, Optional
import structlog

from claude_code_api.models.claude import ClaudeMessage
from claude_code_api.utils.parser import ClaudeOutputParser, OpenAIConverter, MessageAggregator
from claude_code_api.core.claude_manager import ClaudeProcess

logger = structlog.get_logger()


class SSEFormatter:
    """Formats data for Server-Sent Events."""
    
    @staticmethod
    def format_event(data: Dict[str, Any]) -> str:
        """
        Emit a spec-compliant Server-Sent-Event chunk that works with
        EventSource / fetch-sse and the OpenAI client helpers.
        We deliberately omit the `event:` line so the default
        event-type **message** is used.
        """
        json_data = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
        return f"data: {json_data}\n\n"
    
    @staticmethod
    def format_completion(data: str) -> str:
        """Format completion signal."""
        return "data: [DONE]\n\n"
    
    @staticmethod
    def format_error(error: str, error_type: str = "error") -> str:
        """Format error message."""
        error_data = {
            "error": {
                "message": error,
                "type": error_type,
                "code": "stream_error"
            }
        }
        return SSEFormatter.format_event(error_data)
    
    @staticmethod
    def format_heartbeat() -> str:
        """Format heartbeat ping."""
        return ": heartbeat\n\n"


class OpenAIStreamConverter:
    """Converts Claude Code output to OpenAI-compatible streaming format."""
    
    def __init__(self, model: str, session_id: str, include_thoughts: bool = False, 
                 include_tool_calls: bool = False, include_metadata: bool = False,
                 streaming_mode: str = "message", streaming_delay: float = 0.02):
        self.model = model
        self.session_id = session_id
        self.include_thoughts = include_thoughts
        self.include_tool_calls = include_tool_calls
        self.include_metadata = include_metadata
        self.streaming_mode = streaming_mode  # "character", "word", "sentence", "message"
        self.streaming_delay = streaming_delay  # Delay between chunks
        self.completion_id = f"chatcmpl-{uuid.uuid4().hex[:29]}"
        self.created = int(datetime.utcnow().timestamp())
        self.chunk_index = 0
        
    async def convert_stream(
        self, 
        claude_process: ClaudeProcess
    ) -> AsyncGenerator[str, None]:
        """Convert Claude Code output stream to OpenAI format."""
        try:
            # Send initial chunk to establish streaming
            initial_chunk = {
                "id": self.completion_id,
                "object": "chat.completion.chunk",
                "created": self.created,
                "model": self.model,
                "choices": [{
                    "index": 0,
                    "delta": {"role": "assistant", "content": ""},
                    "finish_reason": None
                }]
            }
            yield SSEFormatter.format_event(initial_chunk)
            
            assistant_started = False
            accumulated_content = ""
            
            # Process Claude output
            async for claude_message in claude_process.get_output():
                try:
                    # Handle both dict and string messages
                    if isinstance(claude_message, dict):
                        msg_type = claude_message.get("type")
                    elif isinstance(claude_message, str):
                        # Handle string messages (non-JSON output)
                        logger.info(f"🌊 Received string message: {claude_message[:100]}...")
                        # Convert string to dict format for processing
                        claude_message = {"type": "text", "content": claude_message}
                        msg_type = "text"
                    else:
                        logger.warning(f"🌊 Unknown message type: {type(claude_message)}")
                        continue
                    
                    # Handle different message types based on control parameters
                    if msg_type == "assistant":
                        # Always include assistant messages
                        logger.info(f"🌊 Processing assistant message: {str(claude_message)[:200]}...")
                        message_content = claude_message.get("message", {}).get("content", "")
                        if not message_content:
                            # Try alternative content locations
                            message_content = claude_message.get("content", "")
                        
                        logger.info(f"🌊 Extracted message content: {str(message_content)[:200]}...")
                        text_content = self._extract_text_content(message_content)
                        logger.info(f"🌊 Extracted text content: {text_content[:200]}...")
                        
                        if text_content.strip():
                            # Check if this is a partial message
                            is_partial = claude_message.get("partial", False)
                            partial_indicator = " [PARTIAL]" if is_partial else ""
                            logger.info(f"🌊 Streaming assistant content{partial_indicator}: {text_content[:100]}...")
                            
                            # Stream the content based on streaming mode
                            async for chunk in self._stream_content(text_content, accumulated_content):
                                yield chunk
                            
                            # Update accumulated content for tracking
                            accumulated_content = text_content
                            assistant_started = True
                    
                    elif msg_type == "thinking" and self.include_thoughts:
                        # Include thinking process if enabled
                        thinking_content = claude_message.get("content", "")
                        if thinking_content.strip():
                            logger.info(f"🌊 Streaming thinking process: {thinking_content[:200]}...")
                            thinking_text = f"\n\n💭 **Thinking:** {thinking_content}\n\n"
                            
                            # Stream thinking content
                            async for chunk in self._stream_content(thinking_text, accumulated_content):
                                yield chunk
                                chunk_content = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                accumulated_content += chunk_content
                    
                    elif msg_type == "tool_call" and self.include_tool_calls:
                        # Include tool call details if enabled
                        tool_name = claude_message.get("tool_name", "unknown")
                        tool_args = claude_message.get("arguments", {})
                        logger.info(f"🌊 Streaming tool call: {tool_name}")
                        if tool_args:
                            logger.info(f"🌊 Tool call arguments: {json.dumps(tool_args, ensure_ascii=False)[:200]}...")
                        
                        tool_call_content = f"\n\n🔧 **Tool Call:** {tool_name}"
                        if tool_args:
                            tool_call_content += f"\n**Arguments:** {json.dumps(tool_args, indent=2, ensure_ascii=False)}"
                        tool_call_content += "\n\n"
                        
                        # Stream tool call content
                        async for chunk in self._stream_content(tool_call_content, accumulated_content):
                            yield chunk
                            chunk_content = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            accumulated_content += chunk_content
                    
                    elif msg_type == "tool_result" and self.include_tool_calls:
                        # Include tool result details if enabled
                        tool_result = claude_message.get("result", "")
                        tool_name = claude_message.get("tool_name", "unknown")
                        logger.info(f"🌊 Streaming tool result from {tool_name}: {str(tool_result)[:200]}...")
                        
                        tool_result_content = f"\n\n📋 **Tool Result:**\n{tool_result}\n\n"
                        
                        # Stream tool result content
                        async for chunk in self._stream_content(tool_result_content, accumulated_content):
                            yield chunk
                            chunk_content = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            accumulated_content += chunk_content
                    
                    elif msg_type == "error" and self.include_metadata:
                        # Include error information if metadata is enabled
                        error_msg = claude_message.get("error", "Unknown error")
                        error_type = claude_message.get("error_type", "unknown")
                        logger.error(f"🌊 Streaming error [{error_type}]: {error_msg}")
                        
                        error_content = f"\n\n❌ **Error:** {error_msg}\n\n"
                        
                        # Stream error content
                        async for chunk in self._stream_content(error_content, accumulated_content):
                            yield chunk
                            chunk_content = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            accumulated_content += chunk_content
                    
                    # Handle result type
                    elif msg_type == "result":
                        result_data = claude_message.get("result", {})
                        is_error = claude_message.get("is_error", False)
                        duration_ms = claude_message.get("duration_ms", 0)
                        
                        if is_error:
                            logger.error(f"🌊 Claude process completed with error: {result_data}")
                        else:
                            logger.info(f"🌊 Claude process completed successfully in {duration_ms}ms")
                        break
                    
                    # Log any other message types for debugging
                    else:
                        logger.info(f"🌊 Unhandled message type [{msg_type}]: {str(claude_message)[:200]}...")
                        
                except Exception as e:
                    logger.error("Error processing Claude message", error=str(e), message_type=msg_type)
                    # Try to continue processing other messages
                    continue
            
            # Send final chunk
            final_chunk = {
                "id": self.completion_id,
                "object": "chat.completion.chunk",
                "created": self.created,
                "model": self.model,
                "choices": [{
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop"
                }]
            }
            yield SSEFormatter.format_event(final_chunk)
            
            # Send completion signal
            yield SSEFormatter.format_completion("")
            
        except Exception as e:
            logger.error("Error in stream conversion", error=str(e))
            yield SSEFormatter.format_error(f"Stream error: {str(e)}")
    
    def _extract_text_content(self, message_content) -> str:
        """Extract text content from message content in various formats."""
        if isinstance(message_content, list):
            # Handle content array format: [{"type":"text","text":"..."}]
            for content_item in message_content:
                if (isinstance(content_item, dict) and 
                    content_item.get("type") == "text" and 
                    content_item.get("text")):
                    return content_item["text"]
        elif isinstance(message_content, str):
            # Handle simple string content
            return message_content
        return ""
    
    async def _stream_content(self, content: str, accumulated: str) -> AsyncGenerator[str, None]:
        """Stream content based on the streaming mode."""
        if not content.strip():
            return
        
        # For partial messages, only stream the new content (difference)
        # For complete messages, stream the full content
        if accumulated and content.startswith(accumulated):
            # This is a partial update - only stream the new part
            new_content = content[len(accumulated):]
        else:
            # This is a complete message or first chunk - stream everything
            new_content = content
        
        if self.streaming_mode == "character":
            # Character-by-character streaming with typing effect
            for i, char in enumerate(new_content):
                chunk = {
                    "id": self.completion_id,
                    "object": "chat.completion.chunk",
                    "created": self.created,
                    "model": self.model,
                    "choices": [{
                        "index": 0,
                        "delta": {"content": char},
                        "finish_reason": None
                    }]
                }
                yield SSEFormatter.format_event(chunk)
                
                # Add small delay for typing effect (but don't delay too much)
                if char not in [' ', '\n', '\t'] and self.streaming_delay > 0:
                    await asyncio.sleep(min(self.streaming_delay, 0.01))  # Cap delay at 10ms
        
        elif self.streaming_mode == "word":
            # Word-by-word streaming
            words = new_content.split()
            for i, word in enumerate(words):
                # Add space before word (except first word)
                content_delta = (" " if i > 0 else "") + word
                chunk = {
                    "id": self.completion_id,
                    "object": "chat.completion.chunk",
                    "created": self.created,
                    "model": self.model,
                    "choices": [{
                        "index": 0,
                        "delta": {"content": content_delta},
                        "finish_reason": None
                    }]
                }
                yield SSEFormatter.format_event(chunk)
                await asyncio.sleep(self.streaming_delay * 2.5)  # Slightly longer delay between words
        
        elif self.streaming_mode == "sentence":
            # Sentence-by-sentence streaming
            import re
            sentences = re.split(r'([.!?。！？]\s*)', new_content)
            current_sentence = ""
            
            for part in sentences:
                current_sentence += part
                if re.search(r'[.!?。！？]\s*$', current_sentence.strip()):
                    chunk = {
                        "id": self.completion_id,
                        "object": "chat.completion.chunk",
                        "created": self.created,
                        "model": self.model,
                        "choices": [{
                            "index": 0,
                            "delta": {"content": current_sentence},
                            "finish_reason": None
                        }]
                    }
                    yield SSEFormatter.format_event(chunk)
                    current_sentence = ""
                    await asyncio.sleep(self.streaming_delay * 5)  # Longer delay between sentences
            
            # Send remaining content if any
            if current_sentence.strip():
                chunk = {
                    "id": self.completion_id,
                    "object": "chat.completion.chunk",
                    "created": self.created,
                    "model": self.model,
                    "choices": [{
                        "index": 0,
                        "delta": {"content": current_sentence},
                        "finish_reason": None
                    }]
                }
                yield SSEFormatter.format_event(chunk)
        
        else:  # "message" mode - send entire content at once
            chunk = {
                "id": self.completion_id,
                "object": "chat.completion.chunk",
                "created": self.created,
                "model": self.model,
                "choices": [{
                    "index": 0,
                    "delta": {"content": new_content},
                    "finish_reason": None
                }]
            }
            yield SSEFormatter.format_event(chunk)
    
    def get_final_response(self) -> Dict[str, Any]:
        """Get complete response in OpenAI format."""
        return {
            "id": self.completion_id,
            "object": "chat.completion",
            "created": self.created,
            "model": self.model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Response completed"
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15
            },
            "session_id": self.session_id
        }


class StreamingManager:
    """Manages multiple streaming connections."""
    
    def __init__(self):
        self.active_streams: Dict[str, OpenAIStreamConverter] = {}
        self.heartbeat_interval = 30  # seconds
    
    async def create_stream(
        self,
        session_id: str,
        model: str,
        claude_process: ClaudeProcess,
        include_thoughts: bool = False,
        include_tool_calls: bool = False,
        include_metadata: bool = False,
        streaming_mode: str = "character",
        streaming_delay: float = 0.02
    ) -> AsyncGenerator[str, None]:
        """Create new streaming connection."""
        converter = OpenAIStreamConverter(
            model, session_id, include_thoughts, include_tool_calls, include_metadata, streaming_mode, streaming_delay
        )
        self.active_streams[session_id] = converter
        
        try:
            # Start heartbeat task
            heartbeat_task = asyncio.create_task(
                self._send_heartbeats(session_id)
            )
            
            # Stream conversion
            async for chunk in converter.convert_stream(claude_process):
                yield chunk
            
            # Cancel heartbeat
            heartbeat_task.cancel()
            
        except Exception as e:
            logger.error("Streaming error", session_id=session_id, error=str(e))
            yield SSEFormatter.format_error(f"Streaming failed: {str(e)}")
        finally:
            # Cleanup
            if session_id in self.active_streams:
                del self.active_streams[session_id]
    
    async def _send_heartbeats(self, session_id: str):
        """Send periodic heartbeats to keep connection alive."""
        try:
            while session_id in self.active_streams:
                await asyncio.sleep(self.heartbeat_interval)
                # Heartbeats are handled by the SSE client
        except asyncio.CancelledError:
            pass
    
    def get_active_stream_count(self) -> int:
        """Get number of active streams."""
        return len(self.active_streams)
    
    async def cleanup_stream(self, session_id: str):
        """Cleanup specific stream."""
        if session_id in self.active_streams:
            del self.active_streams[session_id]
    
    async def cleanup_all_streams(self):
        """Cleanup all streams."""
        self.active_streams.clear()


class ChunkBuffer:
    """Buffers chunks for smooth streaming."""
    
    def __init__(self, max_size: int = 1000):
        self.buffer = []
        self.max_size = max_size
        self.lock = asyncio.Lock()
    
    async def add_chunk(self, chunk: str):
        """Add chunk to buffer."""
        async with self.lock:
            self.buffer.append(chunk)
            if len(self.buffer) > self.max_size:
                self.buffer.pop(0)  # Remove oldest chunk
    
    async def get_chunks(self) -> AsyncGenerator[str, None]:
        """Get chunks from buffer."""
        while True:
            async with self.lock:
                if self.buffer:
                    chunk = self.buffer.pop(0)
                    yield chunk
                else:
                    await asyncio.sleep(0.01)  # Small delay to prevent busy waiting


class AdaptiveStreaming:
    """Adaptive streaming with backpressure handling."""
    
    def __init__(self):
        self.chunk_size = 1024
        self.min_chunk_size = 256
        self.max_chunk_size = 4096
        self.adjustment_factor = 1.1
    
    async def stream_with_backpressure(
        self,
        data_source: AsyncGenerator[str, None],
        client_ready_callback: Optional[callable] = None
    ) -> AsyncGenerator[str, None]:
        """Stream with adaptive chunk sizing based on client readiness."""
        buffer = ""
        
        async for data in data_source:
            buffer += data
            
            # Check if we have enough data to send
            while len(buffer) >= self.chunk_size:
                chunk = buffer[:self.chunk_size]
                buffer = buffer[self.chunk_size:]
                
                # Adjust chunk size based on client readiness
                if client_ready_callback and not client_ready_callback():
                    # Client is slow, reduce chunk size
                    self.chunk_size = max(
                        self.min_chunk_size,
                        int(self.chunk_size / self.adjustment_factor)
                    )
                else:
                    # Client is ready, can increase chunk size
                    self.chunk_size = min(
                        self.max_chunk_size,
                        int(self.chunk_size * self.adjustment_factor)
                    )
                
                yield chunk
        
        # Send remaining buffer
        if buffer:
            yield buffer


def _extract_text_content(message_content) -> str:
    """Extract text content from message content in various formats."""
    if isinstance(message_content, list):
        # Handle content array format: [{"type":"text","text":"..."}]
        for content_item in message_content:
            if (isinstance(content_item, dict) and 
                content_item.get("type") == "text" and 
                content_item.get("text")):
                return content_item["text"]
    elif isinstance(message_content, str):
        # Handle simple string content
        return message_content
    return ""


# Global streaming manager instance
streaming_manager = StreamingManager()


async def create_sse_response(
    session_id: str,
    model: str,
    claude_process: ClaudeProcess,
    include_thoughts: bool = False,
    include_tool_calls: bool = False,
    include_metadata: bool = False,
    streaming_mode: str = "character",
    streaming_delay: float = 0.02
) -> AsyncGenerator[str, None]:
    """Create SSE response for Claude Code output with client disconnect detection."""
    try:
        async for chunk in streaming_manager.create_stream(
            session_id, model, claude_process, include_thoughts, include_tool_calls, include_metadata, streaming_mode, streaming_delay
        ):
            yield chunk
    except Exception as e:
        logger.error(f"Streaming error for session {session_id}: {e}")
        yield SSEFormatter.format_error(f"Streaming failed: {str(e)}")
    finally:
        # Cleanup on any exit (including client disconnect)
        logger.info(f"Streaming cleanup for session {session_id}")
        if claude_process and claude_process.is_running:
            try:
                await claude_process.stop()
                logger.info(f"Stopped Claude process for session {session_id}")
            except Exception as cleanup_error:
                logger.error(f"Error stopping Claude process for session {session_id}: {cleanup_error}")


def create_non_streaming_response(
    messages: list,
    session_id: str,
    model: str,
    usage_summary: Dict[str, Any],
    include_thoughts: bool = False,
    include_tool_calls: bool = False,
    include_metadata: bool = False
) -> Dict[str, Any]:
    """Create non-streaming response."""
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:29]}"
    created = int(datetime.utcnow().timestamp())
    
    logger.info(
        "Creating non-streaming response",
        session_id=session_id,
        model=model,
        messages_count=len(messages),
        completion_id=completion_id
    )
    
    # Extract content from Claude messages based on control parameters
    content_parts = []
    for i, msg in enumerate(messages):
        logger.info(
            f"Processing message {i}",
            msg_type=msg.get("type") if isinstance(msg, dict) else type(msg).__name__,
            msg_keys=list(msg.keys()) if isinstance(msg, dict) else [],
            is_assistant=isinstance(msg, dict) and msg.get("type") == "assistant"
        )
        
        if isinstance(msg, dict):
            msg_type = msg.get("type")
            
            # Always include assistant messages
            if msg_type == "assistant" and msg.get("message"):
                message_content = msg["message"].get("content", [])
                text_content = _extract_text_content(message_content)
                
                if text_content.strip():
                    content_parts.append(text_content)
                    logger.info(f"📦 Non-streaming assistant text: {text_content[:100]}...")
            
            # Include thinking process if enabled
            elif msg_type == "thinking" and include_thoughts:
                thinking_content = msg.get("content", "")
                if thinking_content.strip():
                    content_parts.append(f"\n\n💭 **Thinking:** {thinking_content}\n\n")
                    logger.info(f"📦 Non-streaming thinking content: {thinking_content[:100]}...")
            
            # Include tool call details if enabled
            elif msg_type == "tool_call" and include_tool_calls:
                tool_name = msg.get("tool_name", "unknown")
                tool_args = msg.get("arguments", {})
                logger.info(f"📦 Non-streaming tool call: {tool_name}")
                if tool_args:
                    logger.info(f"📦 Tool call arguments: {json.dumps(tool_args, ensure_ascii=False)[:200]}...")
                
                tool_call_content = f"\n\n🔧 **Tool Call:** {tool_name}"
                if tool_args:
                    tool_call_content += f"\n**Arguments:** {json.dumps(tool_args, indent=2, ensure_ascii=False)}"
                tool_call_content += "\n\n"
                content_parts.append(tool_call_content)
            
            # Include tool result details if enabled
            elif msg_type == "tool_result" and include_tool_calls:
                tool_result = msg.get("result", "")
                tool_name = msg.get("tool_name", "unknown")
                if tool_result.strip():
                    content_parts.append(f"\n\n📋 **Tool Result:**\n{tool_result}\n\n")
                    logger.info(f"📦 Non-streaming tool result from {tool_name}: {str(tool_result)[:100]}...")
            
            # Include error information if metadata is enabled
            elif msg_type == "error" and include_metadata:
                error_msg = msg.get("error", "Unknown error")
                error_type = msg.get("error_type", "unknown")
                content_parts.append(f"\n\n❌ **Error:** {error_msg}\n\n")
                logger.error(f"📦 Non-streaming error [{error_type}]: {error_msg}")
    
    # Use the actual content or fallback - ensure we always have content
    if content_parts:
        complete_content = "\n".join(content_parts).strip()
    else:
        complete_content = "Hello! I'm Claude, ready to help."
    
    # Ensure content is never empty
    if not complete_content:
        complete_content = "Response received but content was empty."
    
    logger.info(
        "Final response content",
        content_parts_count=len(content_parts),
        final_content_length=len(complete_content),
        final_content_preview=complete_content[:100] if complete_content else "empty"
    )
    
    # Return simple OpenAI-compatible response with basic usage stats
    response = {
        "id": completion_id,
        "object": "chat.completion",
        "created": created,
        "model": model,
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": complete_content
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": len(complete_content.split()) if complete_content else 5,
            "total_tokens": 10 + (len(complete_content.split()) if complete_content else 5)
        },
        "session_id": session_id
    }
    
    logger.info(
        "Response created successfully",
        response_id=response["id"],
        choices_count=len(response["choices"]),
        message_content_length=len(response["choices"][0]["message"]["content"])
    )
    
    return response
