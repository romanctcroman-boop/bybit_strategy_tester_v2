#!/usr/bin/env python3
"""
DeepSeek Agent CLI Wrapper

Command-line interface for all DeepSeek Agent capabilities:
- analyze: Analyze code for errors
- refactor: Refactor code for better quality
- explain: Explain what code does
- generate: Generate trading strategy code
- insert: Insert code into file
- fix: Fix broken code
- strategy: Generate complete strategy with auto-fix

Usage examples:
    # Analyze file for errors
    python -m backend.agents.deepseek_cli analyze --file backend/core/engine.py --types syntax logic

    # Refactor for performance
    python -m backend.agents.deepseek_cli refactor --file my_code.py --type optimize

    # Explain code
    python -m backend.agents.deepseek_cli explain --code "def add(x,y): return x+y" --focus performance

    # Generate strategy
    python -m backend.agents.deepseek_cli generate --prompt "Create RSI strategy" --symbol BTCUSDT

    # Insert code
    python -m backend.agents.deepseek_cli insert --file strategy.py --code "self.rsi = RSI(14)" --context "__init__"

    # Fix broken code
    python -m backend.agents.deepseek_cli fix --file broken.py --error "SyntaxError: invalid syntax"
"""

import argparse
import asyncio
import sys
from pathlib import Path

from backend.agents.deepseek import CodeGenerationStatus, DeepSeekAgent


def setup_parser() -> argparse.ArgumentParser:
    """Setup CLI argument parser"""
    parser = argparse.ArgumentParser(
        description="DeepSeek Agent CLI - AI-powered code analysis and generation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # ========== ANALYZE COMMAND ==========
    analyze = subparsers.add_parser(
        "analyze",
        help="Analyze code for errors and issues"
    )
    analyze.add_argument(
        "--file",
        required=True,
        help="Path to file to analyze"
    )
    analyze.add_argument(
        "--types",
        nargs="+",
        default=["syntax", "logic", "performance"],
        choices=["syntax", "logic", "performance", "security"],
        help="Types of errors to check (default: syntax logic performance)"
    )
    analyze.add_argument(
        "--output",
        help="Save analysis to file (optional)"
    )
    
    # ========== REFACTOR COMMAND ==========
    refactor = subparsers.add_parser(
        "refactor",
        help="Refactor code for better quality"
    )
    refactor.add_argument(
        "--file",
        required=True,
        help="Path to file to refactor"
    )
    refactor.add_argument(
        "--type",
        required=True,
        choices=["optimize", "extract_function", "inline", "rename"],
        help="Type of refactoring to apply"
    )
    refactor.add_argument(
        "--target",
        help="Target function/variable for refactoring (for rename/extract)"
    )
    refactor.add_argument(
        "--new-name",
        help="New name (for rename refactoring)"
    )
    refactor.add_argument(
        "--output",
        help="Save refactored code to file (optional, otherwise overwrites original)"
    )
    
    # ========== EXPLAIN COMMAND ==========
    explain = subparsers.add_parser(
        "explain",
        help="Explain what code does"
    )
    explain_group = explain.add_mutually_exclusive_group(required=True)
    explain_group.add_argument(
        "--file",
        help="Path to file to explain"
    )
    explain_group.add_argument(
        "--code",
        help="Inline code to explain"
    )
    explain.add_argument(
        "--focus",
        default="all",
        choices=["all", "logic", "performance", "security"],
        help="Focus area for explanation (default: all)"
    )
    explain.add_argument(
        "--no-improvements",
        action="store_true",
        help="Don't include improvement suggestions"
    )
    explain.add_argument(
        "--output",
        help="Save explanation to file (optional)"
    )
    
    # ========== GENERATE COMMAND ==========
    generate = subparsers.add_parser(
        "generate",
        help="Generate trading strategy code"
    )
    generate.add_argument(
        "--prompt",
        required=True,
        help="Strategy description (e.g., 'Create RSI strategy with overbought at 70')"
    )
    generate.add_argument(
        "--symbol",
        default="BTCUSDT",
        help="Trading symbol (default: BTCUSDT)"
    )
    generate.add_argument(
        "--timeframe",
        default="1h",
        help="Timeframe (default: 1h)"
    )
    generate.add_argument(
        "--output",
        help="Save generated code to file (optional)"
    )
    
    # ========== INSERT COMMAND ==========
    insert = subparsers.add_parser(
        "insert",
        help="Insert code into file"
    )
    insert.add_argument(
        "--file",
        required=True,
        help="Target file path"
    )
    insert.add_argument(
        "--code",
        required=True,
        help="Code to insert"
    )
    insert.add_argument(
        "--context",
        help="Context string to search for (e.g., 'def __init__')"
    )
    insert.add_argument(
        "--line",
        type=int,
        help="Line number for insertion (alternative to --context)"
    )
    insert.add_argument(
        "--position",
        default="after",
        choices=["before", "after", "replace"],
        help="Position relative to context/line (default: after)"
    )
    
    # ========== FIX COMMAND ==========
    fix = subparsers.add_parser(
        "fix",
        help="Fix broken code"
    )
    fix.add_argument(
        "--file",
        required=True,
        help="Path to broken file"
    )
    fix.add_argument(
        "--error",
        required=True,
        help="Error message from Python/linter"
    )
    fix.add_argument(
        "--output",
        help="Save fixed code to file (optional, otherwise overwrites original)"
    )
    
    # ========== STRATEGY COMMAND ==========
    strategy = subparsers.add_parser(
        "strategy",
        help="Generate complete strategy with auto-fix"
    )
    strategy.add_argument(
        "--prompt",
        required=True,
        help="Strategy description"
    )
    strategy.add_argument(
        "--symbol",
        default="BTCUSDT",
        help="Trading symbol (default: BTCUSDT)"
    )
    strategy.add_argument(
        "--timeframe",
        default="1h",
        help="Timeframe (default: 1h)"
    )
    strategy.add_argument(
        "--no-auto-fix",
        action="store_true",
        help="Disable automatic error fixing"
    )
    strategy.add_argument(
        "--output",
        required=True,
        help="Save strategy to file"
    )
    
    return parser


async def cmd_analyze(args):
    """Execute analyze command"""
    file_path = Path(args.file)
    
    if not file_path.exists():
        print(f"❌ Error: File not found: {args.file}")
        return 1
    
    print(f"🔍 Analyzing {args.file} for {', '.join(args.types)} errors...")
    
    code = file_path.read_text(encoding='utf-8')
    
    async with DeepSeekAgent() as agent:
        result = await agent.analyze_code(
            code=code,
            file_path=str(file_path),
            error_types=args.types
        )
        
        if result.status == CodeGenerationStatus.COMPLETED:
            print(f"\n✅ Analysis complete ({result.tokens_used} tokens):")
            print("=" * 60)
            print(result.code)
            print("=" * 60)
            
            if args.output:
                Path(args.output).write_text(result.code, encoding='utf-8')
                print(f"\n💾 Saved analysis to {args.output}")
            
            return 0
        else:
            print(f"\n❌ Analysis failed: {result.error}")
            return 1


async def cmd_refactor(args):
    """Execute refactor command"""
    file_path = Path(args.file)
    
    if not file_path.exists():
        print(f"❌ Error: File not found: {args.file}")
        return 1
    
    print(f"🔨 Refactoring {args.file} ({args.type})...")
    
    code = file_path.read_text(encoding='utf-8')
    
    async with DeepSeekAgent() as agent:
        result = await agent.refactor_code(
            code=code,
            refactor_type=args.type,
            target=args.target,
            new_name=args.new_name
        )
        
        if result.status == CodeGenerationStatus.COMPLETED:
            print(f"\n✅ Refactoring complete ({result.tokens_used} tokens)")
            
            output_file = args.output or args.file
            Path(output_file).write_text(result.code, encoding='utf-8')
            print(f"💾 Saved to {output_file}")
            
            return 0
        else:
            print(f"\n❌ Refactoring failed: {result.error}")
            return 1


async def cmd_explain(args):
    """Execute explain command"""
    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"❌ Error: File not found: {args.file}")
            return 1
        code = file_path.read_text(encoding='utf-8')
        print(f"📚 Explaining {args.file}...")
    else:
        code = args.code
        print("📚 Explaining code snippet...")
    
    async with DeepSeekAgent() as agent:
        result = await agent.explain_code(
            code=code,
            focus=args.focus,
            include_improvements=not args.no_improvements
        )
        
        if result.status == CodeGenerationStatus.COMPLETED:
            print(f"\n✅ Explanation complete ({result.tokens_used} tokens):")
            print("=" * 60)
            print(result.code)
            print("=" * 60)
            
            if args.output:
                Path(args.output).write_text(result.code, encoding='utf-8')
                print(f"\n💾 Saved explanation to {args.output}")
            
            return 0
        else:
            print(f"\n❌ Explanation failed: {result.error}")
            return 1


async def cmd_generate(args):
    """Execute generate command"""
    print(f"🚀 Generating strategy: {args.prompt}")
    
    async with DeepSeekAgent() as agent:
        code, tokens = await agent.generate_code(
            prompt=args.prompt,
            context={
                "symbol": args.symbol,
                "timeframe": args.timeframe,
                "task": "trading_strategy"
            }
        )
        
        print(f"\n✅ Generated {len(code)} characters ({tokens} tokens)")
        
        if args.output:
            Path(args.output).write_text(code, encoding='utf-8')
            print(f"💾 Saved to {args.output}")
        else:
            print("\n" + "=" * 60)
            print(code)
            print("=" * 60)
        
        return 0


async def cmd_insert(args):
    """Execute insert command"""
    file_path = Path(args.file)
    
    if not file_path.exists():
        print(f"❌ Error: File not found: {args.file}")
        return 1
    
    if not args.context and args.line is None:
        print("❌ Error: Must specify either --context or --line")
        return 1
    
    print(f"📝 Inserting code into {args.file}...")
    
    async with DeepSeekAgent() as agent:
        result = await agent.insert_code(
            file_path=str(file_path),
            code_to_insert=args.code,
            line_number=args.line,
            context=args.context,
            position=args.position
        )
        
        if result.status == CodeGenerationStatus.COMPLETED:
            print(f"\n✅ {result.code}")
            return 0
        else:
            print(f"\n❌ Insert failed: {result.error}")
            return 1


async def cmd_fix(args):
    """Execute fix command"""
    file_path = Path(args.file)
    
    if not file_path.exists():
        print(f"❌ Error: File not found: {args.file}")
        return 1
    
    print(f"🔧 Fixing {args.file}...")
    
    code = file_path.read_text(encoding='utf-8')
    
    async with DeepSeekAgent() as agent:
        fixed_code, tokens = await agent.fix_code(
            code=code,
            error=args.error,
            original_prompt="Fix code errors"
        )
        
        print(f"\n✅ Fixed code ({tokens} tokens)")
        
        output_file = args.output or args.file
        Path(output_file).write_text(fixed_code, encoding='utf-8')
        print(f"💾 Saved to {output_file}")
        
        return 0


async def cmd_strategy(args):
    """Execute strategy command (with auto-fix)"""
    print(f"🎯 Generating complete strategy: {args.prompt}")
    
    async with DeepSeekAgent() as agent:
        result = await agent.generate_strategy(
            prompt=args.prompt,
            context={
                "symbol": args.symbol,
                "timeframe": args.timeframe
            },
            enable_auto_fix=not args.no_auto_fix
        )
        
        if result.status == CodeGenerationStatus.COMPLETED:
            print("\n✅ Strategy complete!")
            print(f"   Iterations: {result.iterations}")
            print(f"   Tokens used: {result.tokens_used}")
            print(f"   Time: {result.time_elapsed:.2f}s")
            
            Path(args.output).write_text(result.code, encoding='utf-8')
            print(f"💾 Saved to {args.output}")
            
            return 0
        else:
            print(f"\n❌ Strategy generation failed: {result.error}")
            return 1


async def main():
    """Main CLI entry point"""
    parser = setup_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Route to command handler
    commands = {
        "analyze": cmd_analyze,
        "refactor": cmd_refactor,
        "explain": cmd_explain,
        "generate": cmd_generate,
        "insert": cmd_insert,
        "fix": cmd_fix,
        "strategy": cmd_strategy
    }
    
    handler = commands.get(args.command)
    if not handler:
        print(f"❌ Unknown command: {args.command}")
        return 1
    
    try:
        return await handler(args)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        return 130
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
