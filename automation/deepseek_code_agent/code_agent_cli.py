"""
DeepSeek Code Agent CLI - Interactive command-line interface

Quick access to AI-powered code operations:
- Generate code from prompts
- Refactor existing code
- Fix bugs
- Generate tests

Usage:
    python code_agent_cli.py generate "Create a binary search function"
    python code_agent_cli.py refactor myfile.py "Add type hints"
    python code_agent_cli.py fix buggy_code.py "IndexError: list index out of range"
    python code_agent_cli.py test myfile.py

Author: AI Automation System
Date: 2025-11-08
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional

import click
from loguru import logger

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from automation.deepseek_code_agent.code_agent import (
    DeepSeekCodeAgent,
    CodeGenerationRequest,
    CodeRefactorRequest,
    BugFixRequest,
    TestGenerationRequest
)

# Configure logger
logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")


@click.group()
def cli():
    """DeepSeek Code Agent CLI - AI-powered code assistant"""
    pass


@cli.command()
@click.argument('prompt')
@click.option('--lang', default='python', help='Programming language')
@click.option('--style', default='production', type=click.Choice(['production', 'quick', 'experimental']))
@click.option('--context', help='Path to context file')
@click.option('--output', '-o', help='Output file path')
def generate(prompt: str, lang: str, style: str, context: Optional[str], output: Optional[str]):
    """Generate code from natural language prompt
    
    Example:
        code_agent_cli.py generate "Create a REST API client with retry logic"
        code_agent_cli.py generate "Fibonacci with memoization" -o fibonacci.py
    """
    async def _generate():
        agent = DeepSeekCodeAgent()
        
        # Load context if provided
        context_code = None
        if context:
            context_path = Path(context)
            if context_path.exists():
                context_code = context_path.read_text()
                logger.info(f"Loaded context from {context}")
        
        logger.info(f"Generating {lang} code: {prompt}")
        
        result = await agent.generate_code(
            CodeGenerationRequest(
                prompt=prompt,
                language=lang,
                style=style,
                context=context_code
            )
        )
        
        if not result['success']:
            logger.error(f"Generation failed: {result.get('error')}")
            sys.exit(1)
        
        # Print or save result
        if output:
            output_path = Path(output)
            output_path.write_text(result['code'])
            logger.success(f"Code saved to {output}")
        else:
            click.echo("\n" + "="*80)
            click.echo("GENERATED CODE:")
            click.echo("="*80)
            click.echo(result['code'])
            click.echo("\n" + "="*80)
            click.echo("EXPLANATION:")
            click.echo("="*80)
            click.echo(result['explanation'])
            
            if result['suggestions']:
                click.echo("\n" + "="*80)
                click.echo("SUGGESTIONS:")
                click.echo("="*80)
                click.echo(result['suggestions'])
        
        logger.info(f"Usage: {result['usage']}")
        await agent.close()
    
    asyncio.run(_generate())


@cli.command()
@click.argument('file', type=click.Path(exists=True))
@click.argument('instructions')
@click.option('--output', '-o', help='Output file path (default: overwrites input)')
@click.option('--preview', is_flag=True, help='Preview changes without saving')
def refactor(file: str, instructions: str, output: Optional[str], preview: bool):
    """Refactor existing code file
    
    Example:
        code_agent_cli.py refactor mycode.py "Add type hints and docstrings"
        code_agent_cli.py refactor old.py "Use dataclasses" -o new.py
    """
    async def _refactor():
        agent = DeepSeekCodeAgent()
        
        file_path = Path(file)
        original_code = file_path.read_text()
        
        logger.info(f"Refactoring {file}: {instructions}")
        
        result = await agent.refactor_code(
            CodeRefactorRequest(
                code=original_code,
                instructions=instructions,
                language=file_path.suffix.lstrip('.')
            )
        )
        
        if not result['success']:
            logger.error(f"Refactoring failed: {result.get('error')}")
            sys.exit(1)
        
        # Show changes
        click.echo("\n" + "="*80)
        click.echo("CHANGES:")
        click.echo("="*80)
        for i, change in enumerate(result['changes'], 1):
            click.echo(f"{i}. {change}")
        
        click.echo("\n" + "="*80)
        click.echo("EXPLANATION:")
        click.echo("="*80)
        click.echo(result['explanation'])
        
        if preview:
            click.echo("\n" + "="*80)
            click.echo("REFACTORED CODE (PREVIEW):")
            click.echo("="*80)
            click.echo(result['refactored_code'])
        else:
            # Save result
            output_path = Path(output) if output else file_path
            output_path.write_text(result['refactored_code'])
            logger.success(f"Refactored code saved to {output_path}")
        
        logger.info(f"Usage: {result['usage']}")
        await agent.close()
    
    asyncio.run(_refactor())


@cli.command()
@click.argument('file', type=click.Path(exists=True))
@click.argument('error_message')
@click.option('--traceback', help='Path to traceback file')
@click.option('--output', '-o', help='Output file path (default: overwrites input)')
@click.option('--preview', is_flag=True, help='Preview fix without saving')
def fix(file: str, error_message: str, traceback: Optional[str], output: Optional[str], preview: bool):
    """Fix bugs in code with error context
    
    Example:
        code_agent_cli.py fix buggy.py "ZeroDivisionError: division by zero"
        code_agent_cli.py fix code.py "KeyError: 'name'" --traceback tb.txt
    """
    async def _fix():
        agent = DeepSeekCodeAgent()
        
        file_path = Path(file)
        buggy_code = file_path.read_text()
        
        # Load traceback if provided
        tb_text = None
        if traceback:
            tb_path = Path(traceback)
            if tb_path.exists():
                tb_text = tb_path.read_text()
        
        logger.info(f"Fixing error in {file}: {error_message[:50]}...")
        
        result = await agent.fix_errors(
            BugFixRequest(
                code=buggy_code,
                error_message=error_message,
                traceback=tb_text,
                language=file_path.suffix.lstrip('.')
            )
        )
        
        if not result['success']:
            logger.error(f"Bug fix failed: {result.get('error')}")
            sys.exit(1)
        
        # Show analysis
        click.echo("\n" + "="*80)
        click.echo("ROOT CAUSE:")
        click.echo("="*80)
        click.echo(result['root_cause'])
        
        click.echo("\n" + "="*80)
        click.echo("FIX EXPLANATION:")
        click.echo("="*80)
        click.echo(result['fix_explanation'])
        
        click.echo("\n" + "="*80)
        click.echo("PREVENTION:")
        click.echo("="*80)
        click.echo(result['prevention'])
        
        if preview:
            click.echo("\n" + "="*80)
            click.echo("FIXED CODE (PREVIEW):")
            click.echo("="*80)
            click.echo(result['fixed_code'])
        else:
            # Save result
            output_path = Path(output) if output else file_path
            output_path.write_text(result['fixed_code'])
            logger.success(f"Fixed code saved to {output_path}")
        
        logger.info(f"Usage: {result['usage']}")
        await agent.close()
    
    asyncio.run(_fix())


@cli.command()
@click.argument('file', type=click.Path(exists=True))
@click.option('--framework', default='pytest', type=click.Choice(['pytest', 'unittest', 'jest']))
@click.option('--coverage', default='comprehensive', type=click.Choice(['basic', 'comprehensive', 'edge-cases']))
@click.option('--output', '-o', help='Output test file path')
def test(file: str, framework: str, coverage: str, output: Optional[str]):
    """Generate unit tests for code
    
    Example:
        code_agent_cli.py test mymodule.py
        code_agent_cli.py test utils.py --framework unittest -o test_utils.py
    """
    async def _test():
        agent = DeepSeekCodeAgent()
        
        file_path = Path(file)
        code = file_path.read_text()
        
        logger.info(f"Generating {framework} tests for {file}")
        
        result = await agent.generate_tests(
            TestGenerationRequest(
                code=code,
                framework=framework,
                coverage_target=coverage,
                language=file_path.suffix.lstrip('.')
            )
        )
        
        if not result['success']:
            logger.error(f"Test generation failed: {result.get('error')}")
            sys.exit(1)
        
        # Show test cases
        click.echo("\n" + "="*80)
        click.echo("TEST CASES:")
        click.echo("="*80)
        for i, test_case in enumerate(result['test_cases'], 1):
            click.echo(f"{i}. {test_case}")
        
        click.echo("\n" + "="*80)
        click.echo("COVERAGE NOTES:")
        click.echo("="*80)
        click.echo(result['coverage_notes'])
        
        # Save or print tests
        if output:
            output_path = Path(output)
        else:
            # Auto-generate test filename
            output_path = file_path.parent / f"test_{file_path.name}"
        
        output_path.write_text(result['test_code'])
        logger.success(f"Tests saved to {output_path}")
        
        click.echo("\n" + "="*80)
        click.echo("GENERATED TESTS:")
        click.echo("="*80)
        click.echo(result['test_code'])
        
        logger.info(f"Usage: {result['usage']}")
        await agent.close()
    
    asyncio.run(_test())


@cli.command()
def interactive():
    """Start interactive mode"""
    click.echo("🤖 DeepSeek Code Agent - Interactive Mode")
    click.echo("="*80)
    click.echo("Commands:")
    click.echo("  g <prompt>  - Generate code")
    click.echo("  r <file> <instructions> - Refactor code")
    click.echo("  f <file> <error> - Fix bug")
    click.echo("  t <file> - Generate tests")
    click.echo("  q - Quit")
    click.echo("="*80 + "\n")
    
    async def _interactive():
        agent = DeepSeekCodeAgent()
        
        while True:
            try:
                command = click.prompt("\n> ", type=str)
                parts = command.split(maxsplit=1)
                
                if not parts:
                    continue
                
                cmd = parts[0].lower()
                
                if cmd == 'q':
                    break
                elif cmd == 'g' and len(parts) > 1:
                    result = await agent.generate_code(
                        CodeGenerationRequest(prompt=parts[1])
                    )
                    click.echo(f"\n{result['code']}\n")
                elif cmd == 'help':
                    click.echo("Commands: g, r, f, t, q")
                else:
                    click.echo("Unknown command. Type 'help' for commands.")
                    
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Error: {e}")
        
        await agent.close()
        click.echo("\nGoodbye! 👋")
    
    asyncio.run(_interactive())


if __name__ == '__main__':
    cli()
