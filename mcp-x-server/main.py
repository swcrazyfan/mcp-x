import asyncio
import os
import sys
import traceback
from pathlib import Path

# Add the server directory to the path
server_dir = Path(__file__).parent
if str(server_dir) not in sys.path:
    sys.path.append(str(server_dir))

# Import components
from service.x_service import XService
from tools.x_tools import mcp  # Import the mcp instance

# Global X service instance
x_service = None

async def initialize_x_service():
    """Initialize the X service"""
    global x_service
    try:
        # Get data directory from environment variable or use default
        data_dir = os.environ.get("X_DATA_DIR")
        if not data_dir:
            data_dir = os.path.join(os.path.dirname(__file__), "auth", "x_data")
            
        print(f"Initializing X service with data directory: {data_dir}")
        x_service = XService(data_dir=data_dir)
        init_result = await x_service.initialize_client()
        print("X service initialization result:", init_result)
        
        return init_result["status"] == "success"
    except Exception as e:
        print(f"Error initializing X service: {e}")
        traceback.print_exc()
        return False

async def patch_mcp_tool_execution():
    """Patch the MCP server to include x_service in tool calls"""
    global x_service
    
    # Store the original handle_request method
    original_handle_request = mcp.handle_request
    
    # Define a new handle_request method that injects x_service
    async def patched_handle_request(request_id, method, params):
        if method == "execute":
            tool_name = params.get("command")
            tool_params = params.get("params", {})
            
            # Get the tool function
            tool_func = None
            for tool in mcp.tools:
                if tool.name == tool_name:
                    tool_func = tool.func
                    break
            
            if tool_func:
                try:
                    # Call the tool function with x_service as first parameter
                    result = await tool_func(x_service, **tool_params)
                    return {"result": result}
                except Exception as e:
                    error_msg = f"Error executing tool {tool_name}: {str(e)}"
                    print(error_msg)
                    traceback.print_exc()
                    return {"error": {"code": -32000, "message": error_msg}}
            else:
                return {"error": {"code": -32601, "message": f"Tool {tool_name} not found"}}
        
        # For other methods (like initialize), use the original handler
        return await original_handle_request(request_id, method, params)
    
    # Replace the handle_request method
    mcp.handle_request = patched_handle_request
    print(f"Patched MCP server to include x_service in tool calls")

async def main():
    """Main entry point for the MCP server"""
    try:
        # Initialize the X service
        success = await initialize_x_service()
        if not success:
            print("Failed to initialize X service")
            return
        
        # Patch the MCP server to include x_service in tool calls
        await patch_mcp_tool_execution()
        
        # Print available tools
        print(f"Available tools: {[tool.name for tool in mcp.tools]}")
        
        # Run the MCP server
        print("Starting MCP server...")
        await mcp.run_async()
        
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
    finally:
        # Clean up resources
        global x_service
        if x_service is not None:
            await x_service.cleanup()

if __name__ == "__main__":
    # Run the main coroutine
    asyncio.run(main())
