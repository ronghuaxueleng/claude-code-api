"""JSONL parser for Claude Code output."""

import json
import re
from typing import Dict, Any, Optional, List, Generator
from datetime import datetime
import structlog

from claude_code_api.models.claude import ClaudeMessage, ClaudeToolUse, ClaudeToolResult

logger = structlog.get_logger()


class ClaudeOutputParser:
    """Parser for Claude Code JSONL output."""
    
    def __init__(self):
        self.session_id: Optional[str] = None
        self.model: Optional[str] = None
        self.total_tokens = 0
        self.total_cost = 0.0
        self.message_count = 0
    
    def parse_line(self, line: str) -> Optional[ClaudeMessage]:
        """Parse a single JSONL line."""
        if not line.strip():
            return None
        
        try:
            data = json.loads(line.strip())
            message = ClaudeMessage(**data)
            
            # Extract session info on first message
            if message.session_id and not self.session_id:
                self.session_id = message.session_id
            
            if message.model and not self.model:
                self.model = message.model
            
            # Track metrics
            if message.usage:
                input_tokens = message.usage.get("input_tokens", 0)
                output_tokens = message.usage.get("output_tokens", 0)
                self.total_tokens += input_tokens + output_tokens
            
            if message.cost_usd:
                self.total_cost += message.cost_usd
            
            if message.type in ["user", "assistant"]:
                self.message_count += 1
            
            return message
            
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse JSONL line", line=line[:100], error=str(e))
            return None
        except Exception as e:
            logger.error("Error parsing message", line=line[:100], error=str(e))
            return None
    
    def parse_stream(self, lines: List[str]) -> Generator[ClaudeMessage, None, None]:
        """Parse multiple JSONL lines."""
        for line in lines:
            message = self.parse_line(line)
            if message:
                yield message
    
    def extract_text_content(self, message: ClaudeMessage) -> str:
        """Extract text content from a message."""
        if not message.message:
            return ""
        
        content = message.message.get("content", [])
        if isinstance(content, str):
            return content
        
        if isinstance(content, list):
            text_parts = []
            for part in content:
                if isinstance(part, dict):
                    if part.get("type") == "text":
                        text = part.get("text", "")
                        if isinstance(text, str):
                            text_parts.append(text)
                        elif isinstance(text, dict) and "text" in text:
                            text_parts.append(text["text"])
                elif isinstance(part, str):
                    text_parts.append(part)
            return "\n".join(text_parts)
        
        return ""
    
    def extract_tool_uses(self, message: ClaudeMessage) -> List[ClaudeToolUse]:
        """Extract tool uses from a message."""
        if not message.message:
            return []
        
        content = message.message.get("content", [])
        if not isinstance(content, list):
            return []
        
        tool_uses = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "tool_use":
                try:
                    tool_use = ClaudeToolUse(
                        id=part.get("id", ""),
                        name=part.get("name", ""),
                        input=part.get("input", {})
                    )
                    tool_uses.append(tool_use)
                except Exception as e:
                    logger.warning("Failed to parse tool use", part=part, error=str(e))
        
        return tool_uses
    
    def extract_tool_results(self, message: ClaudeMessage) -> List[ClaudeToolResult]:
        """Extract tool results from a message."""
        if not message.message:
            return []
        
        content = message.message.get("content", [])
        if not isinstance(content, list):
            return []
        
        tool_results = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "tool_result":
                try:
                    tool_result = ClaudeToolResult(
                        tool_use_id=part.get("tool_use_id", ""),
                        content=part.get("content", ""),
                        is_error=part.get("is_error", False)
                    )
                    tool_results.append(tool_result)
                except Exception as e:
                    logger.warning("Failed to parse tool result", part=part, error=str(e))
        
        return tool_results
    
    def is_system_message(self, message: ClaudeMessage) -> bool:
        """Check if message is a system message."""
        return message.type == "system"
    
    def is_user_message(self, message: ClaudeMessage) -> bool:
        """Check if message is from user."""
        return (message.type == "user" or 
                (message.message and message.message.get("role") == "user"))
    
    def is_assistant_message(self, message: ClaudeMessage) -> bool:
        """Check if message is from assistant."""
        return (message.type == "assistant" or 
                (message.message and message.message.get("role") == "assistant"))
    
    def is_final_message(self, message: ClaudeMessage) -> bool:
        """Check if this is a final result message."""
        return message.type == "result"
    
    def get_session_summary(self) -> Dict[str, Any]:
        """Get summary of parsed session."""
        return {
            "session_id": self.session_id,
            "model": self.model,
            "total_tokens": self.total_tokens,
            "total_cost": self.total_cost,
            "message_count": self.message_count
        }
    
    def reset(self):
        """Reset parser state."""
        self.session_id = None
        self.model = None
        self.total_tokens = 0
        self.total_cost = 0.0
        self.message_count = 0


class OpenAIConverter:
    """Converts Claude messages to OpenAI format."""
    
    @staticmethod
    def claude_message_to_openai(message: ClaudeMessage) -> Optional[Dict[str, Any]]:
        """Convert Claude message to OpenAI chat format."""
        if message.is_system_message():
            return {
                "role": "system",
                "content": message.extract_text_content()
            }
        
        if message.is_user_message():
            return {
                "role": "user", 
                "content": message.extract_text_content()
            }
        
        if message.is_assistant_message():
            content = message.extract_text_content()
            if content:
                return {
                    "role": "assistant",
                    "content": content
                }
        
        return None
    
    @staticmethod
    def claude_stream_to_openai_chunk(
        message: ClaudeMessage,
        chunk_id: str,
        model: str,
        created: int
    ) -> Optional[Dict[str, Any]]:
        """Convert Claude stream message to OpenAI chunk format."""
        if not message.is_assistant_message():
            return None
        
        content = message.extract_text_content()
        if not content:
            return None
        
        return {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {
                    "role": "assistant",
                    "content": content
                },
                "finish_reason": None
            }]
        }
    
    @staticmethod
    def create_final_chunk(
        chunk_id: str,
        model: str,
        created: int,
        finish_reason: str = "stop"
    ) -> Dict[str, Any]:
        """Create final chunk to end streaming."""
        return {
            "id": chunk_id,
            "object": "chat.completion.chunk", 
            "created": created,
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {},
                "finish_reason": finish_reason
            }]
        }
    
    @staticmethod
    def calculate_usage(parser: ClaudeOutputParser) -> Dict[str, int]:
        """Calculate token usage from parser."""
        # Estimate prompt tokens (this is approximate)
        prompt_tokens = max(0, parser.total_tokens - parser.message_count * 100)
        completion_tokens = parser.total_tokens - prompt_tokens
        
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": parser.total_tokens
        }


class MessageAggregator:
    """Aggregates streaming messages into complete responses."""
    
    def __init__(self):
        self.messages: List[ClaudeMessage] = []
        self.current_assistant_content = ""
        self.parser = ClaudeOutputParser()
    
    def add_message(self, message: ClaudeMessage):
        """Add message to aggregator."""
        self.messages.append(message)
        self.parser.parse_line(message.json())
        
        # Aggregate assistant content for complete response
        if message.is_assistant_message():
            content = self.parser.extract_text_content(message)
            if content:
                self.current_assistant_content += content
    
    def get_complete_response(self) -> str:
        """Get complete aggregated response."""
        return self.current_assistant_content
    
    def get_messages(self) -> List[ClaudeMessage]:
        """Get all messages."""
        return self.messages
    
    def get_usage_summary(self) -> Dict[str, Any]:
        """Get usage summary."""
        return self.parser.get_session_summary()
    
    def clear(self):
        """Clear aggregator state."""
        self.messages.clear()
        self.current_assistant_content = ""
        self.parser.reset()


def sanitize_content(content: str) -> str:
    """Sanitize content for safe transmission."""
    if not content:
        return ""
    
    # Remove null bytes
    content = content.replace('\x00', '')
    
    # Normalize line endings
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    
    # Ensure valid UTF-8
    try:
        content.encode('utf-8')
    except UnicodeEncodeError:
        # Replace invalid characters
        content = content.encode('utf-8', errors='replace').decode('utf-8')
    
    return content


def extract_error_from_message(message: ClaudeMessage) -> Optional[str]:
    """Extract error information from Claude message."""
    if message.error:
        return message.error
    
    if message.type == "result" and not message.result:
        return "Execution completed without result"
    
    # Check for error in tool results
    tool_results = ClaudeOutputParser().extract_tool_results(message)
    for result in tool_results:
        if result.is_error:
            return str(result.content)
    
    return None


def estimate_tokens(text: str) -> int:
    """Rough estimation of token count."""
    # Very rough estimation: ~4 characters per token
    return max(1, len(text) // 4)


def format_timestamp(timestamp: Optional[str]) -> str:
    """Format timestamp for display."""
    if not timestamp:
        return datetime.utcnow().isoformat()
    
    try:
        # Try parsing ISO format
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        return dt.isoformat()
    except:
        return timestamp
