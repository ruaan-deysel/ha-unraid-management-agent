"""
MCP (Model Context Protocol) client for the Unraid Management Agent.

This module provides a client for interacting with the Unraid Management Agent's
MCP server, enabling AI agents to monitor and control Unraid servers.

Example:
    >>> async with UnraidMCPClient("192.168.1.100") as mcp:
    ...     # List available tools
    ...     tools = await mcp.list_tools()
    ...     for tool in tools:
    ...         print(f"{tool.name}: {tool.description}")
    ...
    ...     # Call a tool
    ...     result = await mcp.call_tool("get_system_info", {})
    ...     print(result.content[0].text)
    ...
    ...     # Read a resource
    ...     contents = await mcp.read_resource("unraid://system")
    ...     print(contents[0].text)

"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    import aiohttp


class MCPError(Exception):
    """
    Exception raised for MCP protocol errors.

    Attributes:
        code: JSON-RPC error code
        message: Error message
        data: Additional error data

    """

    def __init__(
        self, message: str, code: int | None = None, data: Any | None = None
    ) -> None:
        self.code = code
        self.message = message
        self.data = data
        super().__init__(f"MCP Error ({code}): {message}" if code else message)


class MCPContent(BaseModel):
    """
    Content item in MCP responses.

    Attributes:
        type: Content type (usually "text")
        text: The content text

    """

    type: str = Field(..., description="Content type")
    text: str = Field(..., description="Content text")

    model_config = {"frozen": True, "extra": "allow"}


class MCPTool(BaseModel):
    """
    MCP tool definition.

    Attributes:
        name: Tool name (e.g., "get_system_info")
        description: Human-readable description
        input_schema: JSON Schema for tool arguments

    """

    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    input_schema: dict[str, Any] = Field(
        default_factory=dict, alias="inputSchema", description="JSON Schema for inputs"
    )

    model_config = {"frozen": True, "extra": "allow", "populate_by_name": True}


class MCPResource(BaseModel):
    """
    MCP resource definition.

    Attributes:
        uri: Resource URI (e.g., "unraid://system")
        name: Resource name
        description: Human-readable description
        mime_type: MIME type of the resource content

    """

    uri: str = Field(..., description="Resource URI")
    name: str = Field(..., description="Resource name")
    description: str = Field("", description="Resource description")
    mime_type: str = Field(
        "application/json", alias="mimeType", description="MIME type"
    )

    model_config = {"frozen": True, "extra": "allow", "populate_by_name": True}


class MCPResourceContent(BaseModel):
    """
    Content of a read resource.

    Attributes:
        uri: Resource URI
        mime_type: MIME type
        text: Resource content as text

    """

    uri: str = Field(..., description="Resource URI")
    mime_type: str = Field(
        "application/json", alias="mimeType", description="MIME type"
    )
    text: str = Field(..., description="Resource content")

    model_config = {"frozen": True, "extra": "allow", "populate_by_name": True}


class MCPPrompt(BaseModel):
    """
    MCP prompt definition.

    Attributes:
        name: Prompt name (e.g., "system_overview")
        description: Human-readable description

    """

    name: str = Field(..., description="Prompt name")
    description: str = Field("", description="Prompt description")

    model_config = {"frozen": True, "extra": "allow"}


class MCPPromptMessage(BaseModel):
    """
    Message in an MCP prompt response.

    Attributes:
        role: Message role (e.g., "user", "assistant")
        content: Message content

    """

    role: str = Field(..., description="Message role")
    content: MCPContent = Field(..., description="Message content")

    model_config = {"frozen": True, "extra": "allow"}


class MCPToolResult(BaseModel):
    """
    Result of an MCP tool call.

    Attributes:
        content: List of content items
        is_error: Whether the result is an error

    """

    content: list[MCPContent] = Field(
        default_factory=list, description="Result content"
    )
    is_error: bool = Field(
        False, alias="isError", description="Whether result is error"
    )

    model_config = {"frozen": True, "extra": "allow", "populate_by_name": True}


class UnraidMCPClient:
    """
    Client for the Unraid Management Agent MCP server.

    This client implements the Model Context Protocol (MCP) for interacting
    with AI agents. It supports listing and calling tools, reading resources,
    and getting prompts.

    Args:
        host: The Unraid server hostname or IP address
        port: The API port (default: 8043)
        timeout: Request timeout in seconds (default: 30)
        use_https: Whether to use HTTPS instead of HTTP (default: False)
        session: Optional aiohttp.ClientSession for session reuse

    Example:
        >>> async with UnraidMCPClient("192.168.1.100") as mcp:
        ...     tools = await mcp.list_tools()
        ...     result = await mcp.call_tool("get_system_info", {})

    """

    def __init__(
        self,
        host: str,
        port: int = 8043,
        timeout: int = 30,
        use_https: bool = False,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.use_https = use_https
        protocol = "https" if use_https else "http"
        self.base_url = f"{protocol}://{host}:{port}/mcp"

        self._session: aiohttp.ClientSession | None = session
        self._owns_session = session is None
        self._request_id = 0

    async def __aenter__(self) -> UnraidMCPClient:
        """Async context manager entry."""
        if self._owns_session:
            import aiohttp

            self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()

    async def close(self) -> None:
        """Close the client session if we own it."""
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None

    def _next_id(self) -> int:
        """Get the next request ID."""
        self._request_id += 1
        return self._request_id

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Ensure we have an active session."""
        if self._session is None:
            import aiohttp

            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    async def _rpc_call(
        self, method: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Make a JSON-RPC call to the MCP server.

        Args:
            method: The RPC method name (e.g., "tools/list")
            params: Optional parameters for the method

        Returns:
            The result field from the JSON-RPC response

        Raises:
            MCPError: If the RPC call fails

        """
        import aiohttp

        session = await self._ensure_session()

        request_data: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
            "id": self._next_id(),
        }
        if params is not None:
            request_data["params"] = params

        try:
            async with session.post(
                self.base_url,
                json=request_data,
                timeout=aiohttp.ClientTimeout(total=self.timeout),
            ) as response:
                data = await response.json()

                if "error" in data:
                    error = data["error"]
                    raise MCPError(
                        message=error.get("message", "Unknown error"),
                        code=error.get("code"),
                        data=error.get("data"),
                    )

                result: dict[str, Any] = data.get("result", {})
                return result

        except aiohttp.ClientError as e:
            raise MCPError(f"Connection error: {e}") from e

    # ==========================================================================
    # Core MCP Methods
    # ==========================================================================

    async def list_tools(self) -> list[MCPTool]:
        """
        List all available MCP tools.

        Returns:
            List of available tools with their schemas

        Example:
            >>> tools = await mcp.list_tools()
            >>> for tool in tools:
            ...     print(f"{tool.name}: {tool.description}")

        """
        result = await self._rpc_call("tools/list")
        tools_data = result.get("tools", [])
        return [MCPTool.model_validate(t) for t in tools_data]

    async def call_tool(
        self, name: str, arguments: dict[str, Any] | None = None
    ) -> MCPToolResult:
        """
        Call an MCP tool.

        Args:
            name: Tool name (e.g., "get_system_info")
            arguments: Tool arguments (optional)

        Returns:
            Tool result containing content and error status

        Example:
            >>> result = await mcp.call_tool("get_system_info", {})
            >>> if not result.is_error:
            ...     data = json.loads(result.content[0].text)
            ...     print(f"Hostname: {data['hostname']}")

        """
        params = {"name": name, "arguments": arguments or {}}
        result = await self._rpc_call("tools/call", params)
        return MCPToolResult.model_validate(result)

    async def list_resources(self) -> list[MCPResource]:
        """
        List all available MCP resources.

        Returns:
            List of available resources

        Example:
            >>> resources = await mcp.list_resources()
            >>> for resource in resources:
            ...     print(f"{resource.uri}: {resource.description}")

        """
        result = await self._rpc_call("resources/list")
        resources_data = result.get("resources", [])
        return [MCPResource.model_validate(r) for r in resources_data]

    async def read_resource(self, uri: str) -> list[MCPResourceContent]:
        """
        Read a resource by URI.

        Args:
            uri: Resource URI (e.g., "unraid://system")

        Returns:
            List of resource contents

        Example:
            >>> contents = await mcp.read_resource("unraid://system")
            >>> data = json.loads(contents[0].text)
            >>> print(f"Hostname: {data['hostname']}")

        """
        params = {"uri": uri}
        result = await self._rpc_call("resources/read", params)
        contents_data = result.get("contents", [])
        return [MCPResourceContent.model_validate(c) for c in contents_data]

    async def list_prompts(self) -> list[MCPPrompt]:
        """
        List all available MCP prompts.

        Returns:
            List of available prompts

        Example:
            >>> prompts = await mcp.list_prompts()
            >>> for prompt in prompts:
            ...     print(f"{prompt.name}: {prompt.description}")

        """
        result = await self._rpc_call("prompts/list")
        prompts_data = result.get("prompts", [])
        return [MCPPrompt.model_validate(p) for p in prompts_data]

    async def get_prompt(
        self, name: str, arguments: dict[str, Any] | None = None
    ) -> list[MCPPromptMessage]:
        """
        Get a prompt by name.

        Args:
            name: Prompt name (e.g., "system_overview")
            arguments: Optional prompt arguments

        Returns:
            List of prompt messages

        Example:
            >>> messages = await mcp.get_prompt("system_overview")
            >>> for msg in messages:
            ...     print(f"{msg.role}: {msg.content.text[:100]}...")

        """
        params = {"name": name, "arguments": arguments or {}}
        result = await self._rpc_call("prompts/get", params)
        messages_data = result.get("messages", [])
        return [MCPPromptMessage.model_validate(m) for m in messages_data]

    # ==========================================================================
    # Convenience Methods
    # ==========================================================================

    async def _call_tool_json(
        self, name: str, arguments: dict[str, Any] | None = None
    ) -> Any:
        """
        Call a tool and parse the JSON response.

        Args:
            name: Tool name
            arguments: Tool arguments

        Returns:
            Parsed JSON data from the tool response

        Raises:
            MCPError: If the tool call fails or returns an error

        """
        result = await self.call_tool(name, arguments)
        if result.is_error:
            error_text = result.content[0].text if result.content else "Unknown error"
            raise MCPError(f"Tool error: {error_text}")
        if not result.content:
            return None
        data: Any = json.loads(result.content[0].text)
        return data

    async def get_system_info(self) -> dict[str, Any]:
        """
        Get system information via MCP.

        Returns:
            System information dictionary

        Example:
            >>> info = await mcp.get_system_info()
            >>> print(f"Hostname: {info['hostname']}")

        """
        result = await self._call_tool_json("get_system_info")
        return dict(result) if result else {}

    async def get_array_status(self) -> dict[str, Any]:
        """
        Get array status via MCP.

        Returns:
            Array status dictionary

        Example:
            >>> status = await mcp.get_array_status()
            >>> print(f"State: {status['state']}")

        """
        result = await self._call_tool_json("get_array_status")
        return dict(result) if result else {}

    async def list_containers(self, state: str | None = None) -> list[dict[str, Any]]:
        """
        List Docker containers via MCP.

        Args:
            state: Optional state filter (e.g., "running")

        Returns:
            List of container dictionaries

        Example:
            >>> containers = await mcp.list_containers(state="running")
            >>> for c in containers:
            ...     print(f"{c['name']}: {c['state']}")

        """
        args = {"state": state} if state else {}
        result = await self._call_tool_json("list_containers", args)
        return list(result) if result else []

    async def container_action(self, container_id: str, action: str) -> MCPToolResult:
        """
        Perform an action on a Docker container.

        Args:
            container_id: Container name or ID
            action: Action to perform (start, stop, restart, pause, unpause)

        Returns:
            Tool result

        Example:
            >>> result = await mcp.container_action("plex", "restart")
            >>> print(result.content[0].text)

        """
        return await self.call_tool(
            "container_action",
            {"container_id": container_id, "action": action},
        )

    async def list_vms(self, state: str | None = None) -> list[dict[str, Any]]:
        """
        List virtual machines via MCP.

        Args:
            state: Optional state filter

        Returns:
            List of VM dictionaries

        """
        args = {"state": state} if state else {}
        result = await self._call_tool_json("list_vms", args)
        return list(result) if result else []

    async def vm_action(self, vm_id: str, action: str) -> MCPToolResult:
        """
        Perform an action on a virtual machine.

        Args:
            vm_id: VM name or ID
            action: Action to perform (start, stop, restart, pause, resume, hibernate, force-stop)

        Returns:
            Tool result

        """
        return await self.call_tool("vm_action", {"vm_id": vm_id, "action": action})

    async def get_disk_info(self, include_smart: bool = False) -> list[dict[str, Any]]:
        """
        Get disk information via MCP.

        Args:
            include_smart: Whether to include SMART data

        Returns:
            List of disk information dictionaries

        """
        result = await self._call_tool_json(
            "list_disks", {"include_smart": include_smart}
        )
        return list(result) if result else []

    async def get_ups_status(self) -> dict[str, Any]:
        """
        Get UPS status via MCP.

        Returns:
            UPS status dictionary

        """
        result = await self._call_tool_json("get_ups_status")
        return dict(result) if result else {}

    async def get_notifications(self) -> dict[str, Any]:
        """
        Get system notifications via MCP.

        Returns:
            Notifications dictionary

        """
        result = await self._call_tool_json("get_notifications")
        return dict(result) if result else {}
