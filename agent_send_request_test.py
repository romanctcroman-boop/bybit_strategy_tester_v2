import asyncio
from backend.agents.unified_agent_interface import get_agent_interface, AgentChannel
from backend.agents.models import AgentRequest, AgentType

async def main():
    ai = get_agent_interface()
    await ai._health_check()
    print('MCP Available:', ai.mcp_available)
    req_ds = AgentRequest(agent_type=AgentType.DEEPSEEK, task_type='analyze', prompt='Short ping test', code=None, context={})
    resp_ds = await ai.send_request(req_ds, preferred_channel=AgentChannel.MCP_SERVER)
    print('DeepSeek success:', resp_ds.success, 'channel:', resp_ds.channel, 'error:', resp_ds.error)
    req_px = AgentRequest(agent_type=AgentType.PERPLEXITY, task_type='analyze', prompt='Short ping test', code=None, context={})
    resp_px = await ai.send_request(req_px, preferred_channel=AgentChannel.MCP_SERVER)
    print('Perplexity success:', resp_px.success, 'channel:', resp_px.channel, 'error:', resp_px.error)

if __name__ == '__main__':
    asyncio.run(main())
