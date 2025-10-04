"""Claude Code process management."""

import asyncio
import json
import os
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Optional, Dict, List, AsyncGenerator, Any
import structlog

from .config import settings

logger = structlog.get_logger()


def _get_fallback_model(primary_model: str) -> Optional[str]:
    """Get fallback model for the given primary model."""
    fallback_map = {
        "kimi-k2-turbo-preview": "kimi-k2-0905-preview",
        "kimi-k2-0905-preview": "kimi-k2-turbo-preview", 
        "claude-3-5-sonnet-20241022": "claude-3-5-haiku-20241022",
        "claude-3-5-haiku-20241022": "claude-3-5-sonnet-20241022",
        "claude-3-opus-20240229": "claude-3-sonnet-20240229",
        "claude-3-sonnet-20240229": "claude-3-haiku-20240307",
        "claude-3-haiku-20240307": "claude-3-sonnet-20240229"
    }
    return fallback_map.get(primary_model)


class ClaudeProcess:
    """Manages a single Claude Code process."""
    
    def __init__(self, session_id: str, project_path: str):
        self.session_id = session_id
        self.project_path = project_path
        self.process: Optional[asyncio.subprocess.Process] = None
        self.is_running = False
        self.output_queue = asyncio.Queue()
        self.error_queue = asyncio.Queue()
        
    async def start(
        self, 
        prompt: str, 
        model: str = None,
        system_prompt: str = None,
        resume_session: str = None,
        provider_config: Dict[str, str] = None
    ) -> bool:
        """Start Claude Code process with real-time output streaming."""
        try:
            # Prepare real command - using correct CLI parameters
            cmd = [settings.claude_binary_path]
            
            # Handle session continuation vs new conversation
            if resume_session:
                # Resume specific session - use -p for non-interactive mode
                cmd.extend(["-p", prompt, "--resume", resume_session])
                logger.info(f"🔄 Resuming session with prompt: {resume_session}")
            else:
                # New conversation - use -p for non-interactive mode
                cmd.extend(["-p", prompt])
                logger.info("🆕 Starting new conversation")
            
            # Add system prompt if provided (only for new conversations)
            if system_prompt and not resume_session:
                cmd.extend(["--append-system-prompt", system_prompt])
            
            # Add model specification
            if model:
                cmd.extend(["--model", model])
            
            # Always use stream-json output format with real-time partial messages
            cmd.extend([
                "--output-format", "stream-json",
                "--verbose", 
                "--dangerously-skip-permissions"
            ])
            
            # Add partial messages support if enabled
            if settings.enable_partial_messages:
                cmd.append("--include-partial-messages")
            
            logger.info(
                "🚀 Starting Claude process",
                session_id=self.session_id,
                project_path=self.project_path,
                model=model or settings.default_model
            )
            
            # Start process from src directory (where Claude works without API key)
            src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            logger.info(f"📁 Working directory: {src_dir}")
            logger.info(f"⚡ Command: {' '.join(cmd)}")
            
            # Prepare environment variables
            env = os.environ.copy()
            if provider_config:
                env.update(provider_config)
                logger.info(f"🔧 Using provider config: {list(provider_config.keys())}")
            
            # Start process with real-time output streaming
            self.process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=src_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env  # Pass environment variables
            )
            
            self.is_running = True
            logger.info(f"✅ Claude process started (PID: {self.process.pid})")
            
            # Start real-time output processing in background
            asyncio.create_task(self._process_output_streams())
            
            # Give the process a moment to start and produce output
            await asyncio.sleep(1)
            
            # Wait for process to complete
            return_code = await self.process.wait()
            self.is_running = False
            
            logger.info(
                "🏁 Claude process completed",
                session_id=self.session_id,
                return_code=return_code
            )
            
            if return_code == 0:
                # Signal end of output
                await self.output_queue.put(None)
                return True
            else:
                # Handle error
                logger.error(f"❌ Claude process failed with exit code {return_code}")
                await self.error_queue.put(f"Process failed with exit code {return_code}")
                await self.error_queue.put(None)
                return False
            
        except Exception as e:
            logger.error(
                "💥 Failed to start Claude process",
                session_id=self.session_id,
                error=str(e)
            )
            return False
    
    async def _process_output_streams(self):
        """Process stdout and stderr streams in real-time."""
        async def read_stdout():
            """Read and process stdout stream."""
            claude_session_id = None
            line_count = 0
            
            try:
                while True:
                    line = await self.process.stdout.readline()
                    if not line:
                        break
                    
                    line_count += 1
                    line_text = line.decode().strip()
                    
                    if line_text:
                        logger.info(f"📤 Claude output [{line_count}]: {line_text[:100]}...")
                        
                        try:
                            data = json.loads(line_text)
                            # Extract Claude's session ID from the first message
                            if not claude_session_id and data.get("session_id"):
                                claude_session_id = data["session_id"]
                                logger.info(f"🆔 Extracted Claude session ID: {claude_session_id}")
                                # Update our session_id to match Claude's
                                self.session_id = claude_session_id
                            
                            await self.output_queue.put(data)
                            
                            # Log message type for debugging
                            msg_type = data.get("type", "unknown")
                            is_partial = data.get("partial", False)
                            
                            if msg_type == "assistant":
                                content = data.get("message", {}).get("content", "")
                                partial_indicator = " [PARTIAL]" if is_partial else ""
                                
                                if isinstance(content, str):
                                    logger.info(f"🤖 Assistant response{partial_indicator}: {content[:100]}...")
                                elif isinstance(content, list):
                                    for item in content:
                                        if isinstance(item, dict) and item.get("type") == "text":
                                            logger.info(f"🤖 Assistant text{partial_indicator}: {item.get('text', '')[:100]}...")
                            
                            elif msg_type == "thinking":
                                thinking_content = data.get("content", "")
                                if thinking_content.strip():
                                    logger.info(f"💭 Thinking process: {thinking_content[:200]}...")
                            
                            elif msg_type == "tool_call":
                                tool_name = data.get("tool_name", "unknown")
                                tool_args = data.get("arguments", {})
                                logger.info(f"🔧 Tool call: {tool_name}")
                                if tool_args:
                                    logger.info(f"🔧 Tool arguments: {json.dumps(tool_args, ensure_ascii=False)[:200]}...")
                            
                            elif msg_type == "tool_result":
                                tool_result = data.get("result", "")
                                tool_name = data.get("tool_name", "unknown")
                                logger.info(f"📋 Tool result from {tool_name}: {str(tool_result)[:200]}...")
                            
                            elif msg_type == "error":
                                error_msg = data.get("error", "Unknown error")
                                error_type = data.get("error_type", "unknown")
                                logger.error(f"❌ Claude error [{error_type}]: {error_msg}")
                            
                            elif msg_type == "system":
                                system_info = data.get("subtype", "unknown")
                                logger.info(f"⚙️  System message: {system_info}")
                            
                            elif msg_type == "user":
                                user_content = data.get("content", "")
                                if isinstance(user_content, str):
                                    logger.info(f"👤 User message: {user_content[:100]}...")
                                elif isinstance(user_content, list):
                                    for item in user_content:
                                        if isinstance(item, dict) and item.get("type") == "text":
                                            logger.info(f"👤 User text: {item.get('text', '')[:100]}...")
                            
                            else:
                                logger.info(f"📨 Unknown message type [{msg_type}]: {str(data)[:100]}...")
                            
                        except json.JSONDecodeError:
                            # Handle non-JSON output
                            logger.info(f"📝 Non-JSON output: {line_text}")
                            await self.output_queue.put({"type": "text", "content": line_text})
            except Exception as e:
                logger.error(f"Error reading stdout: {e}")
                # Put error in queue to signal end
                await self.output_queue.put({"type": "error", "error": str(e)})
        
        async def read_stderr():
            """Read and process stderr stream."""
            try:
                while True:
                    line = await self.process.stderr.readline()
                    if not line:
                        break
                    
                    line_text = line.decode().strip()
                    if line_text:
                        logger.warning(f"⚠️  Claude stderr: {line_text}")
                        await self.error_queue.put(line_text)
            except Exception as e:
                logger.error(f"Error reading stderr: {e}")
        
        # Start both readers concurrently
        await asyncio.gather(
            read_stdout(),
            read_stderr(),
            return_exceptions=True
        )
    
    
    async def get_output(self) -> AsyncGenerator[Dict[str, Any], None]:
        """Get output from Claude process."""
        timeout_count = 0
        max_timeouts = 3  # Allow up to 3 timeouts before giving up
        
        while True:
            try:
                # Wait for output with shorter timeout
                output = await asyncio.wait_for(
                    self.output_queue.get(),
                    timeout=10  # 10 second timeout instead of 30
                )
                
                if output is None:  # End signal
                    break
                    
                yield output
                timeout_count = 0  # Reset timeout count on successful output
                
            except asyncio.TimeoutError:
                timeout_count += 1
                logger.warning(
                    "Output timeout",
                    session_id=self.session_id,
                    timeout_count=timeout_count,
                    max_timeouts=max_timeouts
                )
                
                # If we've timed out too many times, give up
                if timeout_count >= max_timeouts:
                    logger.error(
                        "Too many timeouts, stopping output collection",
                        session_id=self.session_id
                    )
                    break
                    
            except Exception as e:
                logger.error(
                    "Error getting output",
                    session_id=self.session_id,
                    error=str(e)
                )
                break
    
    
    async def _start_mock_process(self, prompt: str, model: str):
        """Start mock process for testing."""
        self.is_running = True
        
        # Create mock Claude response
        mock_response = {
            "type": "result",
            "sessionId": self.session_id,
            "model": model or "claude-3-5-haiku-20241022",
            "message": {
                "role": "assistant", 
                "content": f"Hello! You said: '{prompt}'. This is a mock response from Claude Code API Gateway."
            },
            "usage": {
                "input_tokens": len(prompt.split()),
                "output_tokens": 15,
                "total_tokens": len(prompt.split()) + 15
            },
            "cost_usd": 0.001,
            "duration_ms": 100
        }
        
        # Put the response in the queue
        await self.output_queue.put(mock_response)
        await self.output_queue.put(None)  # End signal
    
    async def stop(self):
        """Stop Claude process."""
        self.is_running = False
        
        if self.process:
            try:
                # First try graceful termination
                self.process.terminate()
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=3.0)
                except asyncio.TimeoutError:
                    # Force kill if graceful termination fails
                    logger.warning(f"Process {self.process.pid} didn't terminate gracefully, forcing kill")
                    self.process.kill()
                    await self.process.wait()
            except Exception as e:
                logger.error(
                    "Error stopping process",
                    session_id=self.session_id,
                    error=str(e)
                )
            finally:
                self.process = None
        
        logger.info(
            "Claude process stopped",
            session_id=self.session_id
        )


class ClaudeManager:
    """Manages multiple Claude Code processes."""
    
    def __init__(self):
        self.processes: Dict[str, ClaudeProcess] = {}
        self.max_concurrent = settings.max_concurrent_sessions
    
    async def get_version(self) -> str:
        """Get Claude Code version."""
        try:
            result = await asyncio.create_subprocess_exec(
                settings.claude_binary_path,
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                version = stdout.decode().strip()
                return version
            else:
                error = stderr.decode().strip()
                raise Exception(f"Claude version check failed: {error}")
                
        except FileNotFoundError:
            raise Exception(f"Claude binary not found at: {settings.claude_binary_path}")
        except Exception as e:
            raise Exception(f"Failed to get Claude version: {str(e)}")
    
    async def create_session(
        self,
        session_id: str,
        project_path: str,
        prompt: str,
        model: str = None,
        system_prompt: str = None,
        resume_session: str = None,
        provider_config: Dict[str, str] = None
    ) -> ClaudeProcess:
        """Create new Claude session or resume existing one."""
        # Check concurrent session limit
        if len(self.processes) >= self.max_concurrent:
            raise Exception(f"Maximum concurrent sessions ({self.max_concurrent}) reached")
        
        # Ensure project directory exists
        os.makedirs(project_path, exist_ok=True)
        
        # Determine if this is a session resume
        is_resume = resume_session is not None
        
        if is_resume:
            logger.info(f"🔄 Resuming existing session: {resume_session}")
            # Use the resume_session as the session_id for resumed sessions
            actual_session_id = resume_session
        else:
            logger.info(f"🆕 Creating new session: {session_id}")
            actual_session_id = session_id
        
        # Create process
        process = ClaudeProcess(actual_session_id, project_path)
        
        # Start process
        success = await process.start(
            prompt=prompt,
            model=model or settings.default_model,
            system_prompt=system_prompt,
            resume_session=resume_session,
            provider_config=provider_config
        )
        
        if not success:
            raise Exception("Failed to start Claude process")
        
        # Don't store processes since Claude CLI completes immediately
        # This prevents the "max concurrent sessions" error
        
        logger.info(
            "Claude session created",
            session_id=process.session_id,  # Use Claude's actual session ID
            is_resume=is_resume,
            active_sessions=len(self.processes)
        )
        
        return process
    
    async def get_session(self, session_id: str) -> Optional[ClaudeProcess]:
        """Get existing Claude session."""
        return self.processes.get(session_id)
    
    async def stop_session(self, session_id: str):
        """Stop Claude session."""
        if session_id in self.processes:
            process = self.processes[session_id]
            await process.stop()
            del self.processes[session_id]
            
            logger.info(
                "Claude session stopped",
                session_id=session_id,
                active_sessions=len(self.processes)
            )
    
    async def cleanup_all(self):
        """Stop all Claude sessions."""
        logger.info(f"Cleaning up {len(self.processes)} Claude processes")
        
        # Create a list of tasks to clean up all processes concurrently
        cleanup_tasks = []
        for session_id in list(self.processes.keys()):
            task = asyncio.create_task(self.stop_session(session_id))
            cleanup_tasks.append(task)
        
        # Wait for all cleanup tasks to complete
        if cleanup_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*cleanup_tasks, return_exceptions=True),
                    timeout=10.0
                )
            except asyncio.TimeoutError:
                logger.warning("Some processes didn't clean up within timeout")
        
        logger.info("All Claude sessions cleaned up")
    
    def get_active_sessions(self) -> List[str]:
        """Get list of active session IDs."""
        return list(self.processes.keys())
    
    async def check_zombie_processes(self):
        """Check for and clean up zombie processes."""
        zombie_sessions = []
        for session_id, process in self.processes.items():
            if process.process and process.process.returncode is not None:
                # Process has completed but wasn't cleaned up
                zombie_sessions.append(session_id)
                logger.warning(f"Found zombie process for session {session_id}")
        
        # Clean up zombie processes
        for session_id in zombie_sessions:
            await self.stop_session(session_id)
            logger.info(f"Cleaned up zombie process for session {session_id}")
        
        return len(zombie_sessions)
    
    async def continue_conversation(
        self,
        session_id: str,
        prompt: str
    ) -> bool:
        """Continue existing conversation."""
        # For non-interactive mode, we need to start a new process with the prompt
        # This method is kept for API compatibility but may not be used
        logger.warning("continue_conversation called but not supported in non-interactive mode")
        return False


# Utility functions for project management
def create_project_directory(project_id: str) -> str:
    """Create project directory."""
    project_path = os.path.join(settings.project_root, project_id)
    os.makedirs(project_path, exist_ok=True)
    return project_path


def cleanup_project_directory(project_path: str):
    """Clean up project directory."""
    try:
        import shutil
        if os.path.exists(project_path):
            shutil.rmtree(project_path)
            logger.info("Project directory cleaned up", path=project_path)
    except Exception as e:
        logger.error("Failed to cleanup project directory", path=project_path, error=str(e))


def validate_claude_binary() -> bool:
    """Validate Claude binary availability."""
    try:
        result = subprocess.run(
            [settings.claude_binary_path, "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except Exception:
        return False
