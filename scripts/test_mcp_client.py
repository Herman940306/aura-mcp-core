import asyncio
import logging
import sys

from mcp.client.session import ClientSession
from mcp.client.sse import sse_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("mcp_client_test")


async def run():
    url = "http://localhost:9200/sse"
    logger.info(f"Connecting to Aura IA MCP server at {url}...")

    try:
        async with sse_client(url) as (read, write):
            logger.info("Connected to SSE endpoint.")

            async with ClientSession(read, write) as session:
                logger.info("Initializing session...")
                await session.initialize()
                logger.info("Session initialized.")

                # List tools
                logger.info("Listing tools...")
                tools_result = await session.list_tools()
                tools = tools_result.tools
                logger.info(f"Found {len(tools)} tools.")

                for tool in tools:
                    logger.info(f"Tool: {tool.name}")

                # Call ide_agents_health
                logger.info("Calling ide_agents_health...")
                health_result = await session.call_tool(
                    "ide_agents_health", {}
                )
                logger.info(f"Health result: {health_result}")

                # Call ide_agents_metrics_snapshot
                logger.info("Calling ide_agents_metrics_snapshot...")
                metrics_result = await session.call_tool(
                    "ide_agents_metrics_snapshot", {}
                )
                logger.info(f"Metrics result: {metrics_result}")

    except Exception as e:
        logger.error(f"Error during MCP test: {e}")
        raise


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
