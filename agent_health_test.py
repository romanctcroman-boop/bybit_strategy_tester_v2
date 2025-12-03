import asyncio, json
from backend.agents.unified_agent_interface import get_agent_interface, AgentRequest, AgentType

async def main():
    ai = get_agent_interface()
    await ai._health_check()
    print('HEALTH STATS:\n', json.dumps(ai.get_stats(), indent=2))
    req = AgentRequest(agent_type=AgentType.DEEPSEEK, task_type='analyze', prompt='Ping test', code=None, context={})
    resp = await ai.send_request(req)
    print('DEEPSEEK SUCCESS:', resp.success)
    if not resp.success:
        print('DEEPSEEK ERROR:', resp.error)
    else:
        snippet = resp.content if isinstance(resp.content, str) else str(resp.content)
        print('DEEPSEEK CONTENT SNIPPET:', snippet[:200])

if __name__ == '__main__':
    asyncio.run(main())
