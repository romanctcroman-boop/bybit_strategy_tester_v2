import asyncio, json
from backend.agents.unified_agent_interface import get_agent_interface, AgentRequest, AgentType

async def main():
    ai = get_agent_interface()
    await ai._health_check()
    print('HEALTH STATS:\n', json.dumps(ai.get_stats(), indent=2))
    req = AgentRequest(agent_type=AgentType.DEEPSEEK, task_type='analyze', prompt='Ping test', code=None, context={})
    resp = await ai.execute(req)
    print('DEEPSEEK SUCCESS:', resp.get('success'))
    if not resp.get('success'):
        print('DEEPSEEK ERROR:', resp.get('error'))
    else:
        print('DEEPSEEK CONTENT SNIPPET:', str(resp.get('content'))[:200])

if __name__ == '__main__':
    asyncio.run(main())
