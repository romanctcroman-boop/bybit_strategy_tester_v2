"""
DeepSeek Agent Usage Examples

Demonstrates all 7 methods of DeepSeek Agent with real-world scenarios.
Run each example independently to see agent capabilities.

Installation:
    pip install aiohttp pandas

Usage:
    python examples/deepseek_agent_examples.py
"""

import asyncio
from pathlib import Path
from backend.agents.deepseek import DeepSeekAgent, CodeGenerationStatus


# ========== EXAMPLE 1: Generate Trading Strategy ==========

async def example_1_generate_strategy():
    """Generate a complete trading strategy from natural language"""
    print("\n" + "=" * 60)
    print("Example 1: Generate Trading Strategy")
    print("=" * 60)
    
    async with DeepSeekAgent() as agent:
        code, tokens = await agent.generate_code(
            prompt="Create a Bollinger Bands breakout strategy with 20-period SMA and 2 standard deviations",
            context={
                "symbol": "BTCUSDT",
                "timeframe": "1h",
                "task": "trading_strategy"
            }
        )
        
        print(f"✅ Generated {len(code)} characters using {tokens} tokens\n")
        print("Generated Code Preview:")
        print("-" * 60)
        print(code[:500] + "...\n")


# ========== EXAMPLE 2: Analyze Code for Errors ==========

async def example_2_analyze_code():
    """Analyze code for logic errors and performance issues"""
    print("\n" + "=" * 60)
    print("Example 2: Analyze Code for Errors")
    print("=" * 60)
    
    # Example code with issues
    problematic_code = """
def calculate_profit(trades):
    total = 0
    for trade in trades:
        profit = trade['exit_price'] / trade['entry_price']  # Should be subtraction
        total += profit
    return total / len(trades)  # Division by zero if empty

def fibonacci(n):
    return fibonacci(n-1) + fibonacci(n-2)  # Missing base case
"""
    
    async with DeepSeekAgent() as agent:
        result = await agent.analyze_code(
            code=problematic_code,
            error_types=["logic", "performance"]
        )
        
        if result.status == CodeGenerationStatus.COMPLETED:
            print(f"✅ Analysis complete ({result.tokens_used} tokens)\n")
            print("Analysis Results:")
            print("-" * 60)
            print(result.code)
        else:
            print(f"❌ Analysis failed: {result.error}")


# ========== EXAMPLE 3: Refactor Code for Performance ==========

async def example_3_refactor_for_performance():
    """Refactor inefficient code to improve performance"""
    print("\n" + "=" * 60)
    print("Example 3: Refactor for Performance")
    print("=" * 60)
    
    slow_code = """
def process_signals(df):
    results = []
    for i in range(len(df)):
        if df.iloc[i]['rsi'] > 70:
            results.append({'type': 'overbought', 'price': df.iloc[i]['close']})
        elif df.iloc[i]['rsi'] < 30:
            results.append({'type': 'oversold', 'price': df.iloc[i]['close']})
    return results
"""
    
    async with DeepSeekAgent() as agent:
        result = await agent.refactor_code(
            code=slow_code,
            refactor_type="optimize"
        )
        
        if result.status == CodeGenerationStatus.COMPLETED:
            print(f"✅ Refactored ({result.tokens_used} tokens)\n")
            print("Optimized Code:")
            print("-" * 60)
            print(result.code[:500] + "...")
        else:
            print(f"❌ Refactoring failed: {result.error}")


# ========== EXAMPLE 4: Explain Complex Algorithm ==========

async def example_4_explain_algorithm():
    """Get detailed explanation of a complex algorithm"""
    print("\n" + "=" * 60)
    print("Example 4: Explain Complex Algorithm")
    print("=" * 60)
    
    complex_code = """
def kalman_filter(measurements, initial_estimate=0, initial_error=1, 
                  process_variance=0.001, measurement_variance=0.1):
    estimates = []
    estimate = initial_estimate
    error_estimate = initial_error
    
    for measurement in measurements:
        # Prediction
        error_estimate = error_estimate + process_variance
        
        # Update
        kalman_gain = error_estimate / (error_estimate + measurement_variance)
        estimate = estimate + kalman_gain * (measurement - estimate)
        error_estimate = (1 - kalman_gain) * error_estimate
        
        estimates.append(estimate)
    
    return estimates
"""
    
    async with DeepSeekAgent() as agent:
        result = await agent.explain_code(
            code=complex_code,
            focus="logic",
            include_improvements=True
        )
        
        if result.status == CodeGenerationStatus.COMPLETED:
            print(f"✅ Explanation complete ({result.tokens_used} tokens)\n")
            print("Explanation:")
            print("-" * 60)
            print(result.code[:800] + "...")
        else:
            print(f"❌ Explanation failed: {result.error}")


# ========== EXAMPLE 5: Fix Broken Code ==========

async def example_5_fix_broken_code():
    """Automatically fix syntax and logic errors"""
    print("\n" + "=" * 60)
    print("Example 5: Fix Broken Code")
    print("=" * 60)
    
    broken_code = """
def calculate_rsi(prices, period=14)
    gains = []
    losses = []
    
    for i in range(1, len(prices)):
        change = prices[i] - prices[i-1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else
            gains.append(0)
            losses.append(abs(change))
    
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return rsi
"""
    
    async with DeepSeekAgent() as agent:
        fixed_code, tokens = await agent.fix_code(
            code=broken_code,
            error="SyntaxError: invalid syntax (missing colons)",
            original_prompt="Calculate RSI indicator"
        )
        
        print(f"✅ Fixed code ({tokens} tokens)\n")
        print("Fixed Code:")
        print("-" * 60)
        print(fixed_code[:500] + "...")


# ========== EXAMPLE 6: Insert Code into File ==========

async def example_6_insert_code():
    """Insert code snippet into existing file"""
    print("\n" + "=" * 60)
    print("Example 6: Insert Code into File")
    print("=" * 60)
    
    # Create temporary test file
    test_file = Path("temp_strategy.py")
    test_file.write_text("""
class MyStrategy:
    def __init__(self):
        self.name = "Test Strategy"
    
    def generate_signals(self, df):
        return df
""")
    
    async with DeepSeekAgent() as agent:
        result = await agent.insert_code(
            file_path=str(test_file),
            code_to_insert="        self.rsi_period = 14\n        self.rsi = None",
            context="def __init__(self):",
            position="after"
        )
        
        if result.status == CodeGenerationStatus.COMPLETED:
            print(f"✅ {result.code}\n")
            
            # Show updated file
            updated_content = test_file.read_text()
            print("Updated File:")
            print("-" * 60)
            print(updated_content)
            
            # Cleanup
            test_file.unlink()
        else:
            print(f"❌ Insert failed: {result.error}")


# ========== EXAMPLE 7: Complete Strategy with Auto-Fix ==========

async def example_7_complete_strategy_with_autofix():
    """Generate complete strategy with automatic error fixing"""
    print("\n" + "=" * 60)
    print("Example 7: Complete Strategy with Auto-Fix")
    print("=" * 60)
    
    async with DeepSeekAgent() as agent:
        result = await agent.generate_strategy(
            prompt="Create a mean reversion strategy using RSI (overbought at 70, oversold at 30) with position sizing based on volatility",
            context={
                "symbol": "ETHUSDT",
                "timeframe": "4h",
                "initial_capital": 10000
            },
            enable_auto_fix=True
        )
        
        if result.status == CodeGenerationStatus.COMPLETED:
            print(f"✅ Strategy complete!")
            print(f"   Status: {result.status.value}")
            print(f"   Iterations: {result.iterations}")
            print(f"   Tokens used: {result.tokens_used}")
            print(f"   Time elapsed: {result.time_elapsed:.2f}s\n")
            
            print("Generated Strategy Preview:")
            print("-" * 60)
            print(result.code[:600] + "...\n")
            
            # Save to file
            output_file = Path("generated_mean_reversion_strategy.py")
            output_file.write_text(result.code)
            print(f"💾 Saved to {output_file}")
        else:
            print(f"❌ Strategy generation failed: {result.error}")


# ========== BATCH PROCESSING EXAMPLE ==========

async def example_8_batch_analysis():
    """Analyze multiple files in batch"""
    print("\n" + "=" * 60)
    print("Example 8: Batch Analysis")
    print("=" * 60)
    
    files_to_analyze = [
        ("file1.py", "def add(x,y): return x/y"),  # Division by zero risk
        ("file2.py", "def loop(): while True: pass"),  # Infinite loop
        ("file3.py", "password = 'hardcoded123'")  # Security issue
    ]
    
    async with DeepSeekAgent() as agent:
        for filename, code in files_to_analyze:
            print(f"\n🔍 Analyzing {filename}...")
            
            result = await agent.analyze_code(
                code=code,
                file_path=filename,
                error_types=["logic", "security"]
            )
            
            if result.status == CodeGenerationStatus.COMPLETED:
                print(f"✅ Analysis complete")
                print(result.code[:200] + "...")
            else:
                print(f"❌ Failed: {result.error}")


# ========== INTERACTIVE EXAMPLE ==========

async def example_9_interactive_workflow():
    """Interactive workflow: generate → analyze → refactor → explain"""
    print("\n" + "=" * 60)
    print("Example 9: Interactive Workflow")
    print("=" * 60)
    
    async with DeepSeekAgent() as agent:
        # Step 1: Generate
        print("\n1️⃣ Generating initial code...")
        code, gen_tokens = await agent.generate_code(
            prompt="Create function to calculate moving average",
            context={"task": "indicator"}
        )
        print(f"✅ Generated ({gen_tokens} tokens)")
        
        # Step 2: Analyze
        print("\n2️⃣ Analyzing for issues...")
        analysis = await agent.analyze_code(
            code=code,
            error_types=["logic", "performance"]
        )
        print(f"✅ Analyzed ({analysis.tokens_used} tokens)")
        
        # Step 3: Refactor
        print("\n3️⃣ Refactoring for optimization...")
        refactored = await agent.refactor_code(
            code=code,
            refactor_type="optimize"
        )
        print(f"✅ Refactored ({refactored.tokens_used} tokens)")
        
        # Step 4: Explain
        print("\n4️⃣ Explaining final code...")
        explanation = await agent.explain_code(
            code=refactored.code,
            focus="performance"
        )
        print(f"✅ Explained ({explanation.tokens_used} tokens)")
        
        total_tokens = gen_tokens + analysis.tokens_used + refactored.tokens_used + explanation.tokens_used
        print(f"\n📊 Total tokens used: {total_tokens}")


# ========== MAIN RUNNER ==========

async def run_all_examples():
    """Run all examples sequentially"""
    examples = [
        ("Generate Strategy", example_1_generate_strategy),
        ("Analyze Code", example_2_analyze_code),
        ("Refactor Performance", example_3_refactor_for_performance),
        ("Explain Algorithm", example_4_explain_algorithm),
        ("Fix Broken Code", example_5_fix_broken_code),
        ("Insert Code", example_6_insert_code),
        ("Complete Strategy with Auto-Fix", example_7_complete_strategy_with_autofix),
        ("Batch Analysis", example_8_batch_analysis),
        ("Interactive Workflow", example_9_interactive_workflow)
    ]
    
    print("\n" + "=" * 60)
    print("DeepSeek Agent - All Examples")
    print("=" * 60)
    print(f"\nRunning {len(examples)} examples...\n")
    
    for i, (name, func) in enumerate(examples, 1):
        try:
            await func()
        except KeyboardInterrupt:
            print(f"\n\n⚠️  Interrupted at example {i}")
            break
        except Exception as e:
            print(f"\n❌ Example {i} failed: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)


async def run_single_example(example_number: int):
    """Run a specific example by number"""
    examples = {
        1: example_1_generate_strategy,
        2: example_2_analyze_code,
        3: example_3_refactor_for_performance,
        4: example_4_explain_algorithm,
        5: example_5_fix_broken_code,
        6: example_6_insert_code,
        7: example_7_complete_strategy_with_autofix,
        8: example_8_batch_analysis,
        9: example_9_interactive_workflow
    }
    
    if example_number not in examples:
        print(f"❌ Invalid example number: {example_number}")
        print(f"Available examples: 1-{len(examples)}")
        return
    
    await examples[example_number]()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # Run specific example
        try:
            example_num = int(sys.argv[1])
            asyncio.run(run_single_example(example_num))
        except ValueError:
            print("❌ Invalid example number")
            print("Usage: python examples/deepseek_agent_examples.py [1-9]")
    else:
        # Run all examples
        asyncio.run(run_all_examples())
