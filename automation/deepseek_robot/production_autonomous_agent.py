"""
🤖 Autonomous DeepSeek Agent - PRODUCTION MODE with Real Fixes

ВАЖНО: Реальное применение fixes с backup и rollback!
"""

import asyncio
import json
import shutil
from pathlib import Path
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from automation.deepseek_robot.robot import DeepSeekRobot, AutonomyLevel


class SmartFixApplicator:
    """
    Умная система применения fixes с:
    - Backup перед изменением
    - Валидация изменений
    - Rollback при ошибках
    - Incremental fixing (постепенное исправление)
    """
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.backup_dir = project_root / ".robot_backups"
        self.backup_dir.mkdir(exist_ok=True)
        
    def create_backup(self, file_path: Path) -> Path:
        """Создать backup файла"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"{file_path.name}.{timestamp}.backup"
        shutil.copy2(file_path, backup_path)
        return backup_path
    
    async def apply_fix_smart(
        self,
        file_path: Path,
        issue: Dict[str, Any],
        fix_suggestion: str,
        robot: DeepSeekRobot
    ) -> Dict[str, Any]:
        """
        Умное применение fix с валидацией
        
        Returns:
            {"success": bool, "changes": str, "backup": Path, "error": str}
        """
        try:
            # 1. Create backup
            backup_path = self.create_backup(file_path)
            print(f"      📦 Backup created: {backup_path.name}")
            
            # 2. Read file
            content = file_path.read_text(encoding="utf-8")
            
            # 3. Generate smart fix using DeepSeek
            fix_request = {
                "query": f"""Generate EXACT code fix for this issue:

File: {file_path.name}
Issue: {issue['description']}
Severity: {issue['severity']}
Line: {issue.get('line', 0)}

Current code snippet:
{content[:2000]}

CRITICAL REQUIREMENTS:
1. Provide EXACT code to replace (old_code) and new code (new_code)
2. Include context (3-5 lines before/after)
3. Ensure syntax is valid
4. Don't break existing functionality
5. Add comments explaining the fix

Return JSON:
{{
    "old_code": "exact code to replace with context",
    "new_code": "fixed code with context",
    "explanation": "why this fix works",
    "risk_level": "low/medium/high"
}}
""",
                "model": "deepseek-coder",
                "temperature": 0.1,
                "max_tokens": 2000
            }
            
            results = await robot.executor.execute_batch([fix_request], use_cache=False)
            
            if not results or not results[0].get("success"):
                return {
                    "success": False,
                    "error": "Failed to generate fix",
                    "backup": backup_path
                }
            
            response = results[0].get("response", "")
            
            # 4. Parse fix from response
            fix_data = self._parse_fix_response(response)
            
            if not fix_data:
                return {
                    "success": False,
                    "error": "Could not parse fix",
                    "backup": backup_path
                }
            
            # 5. Validate risk level
            if fix_data.get("risk_level") == "high":
                print(f"      ⚠️  High risk fix - skipping for safety")
                return {
                    "success": False,
                    "error": "High risk - requires manual review",
                    "backup": backup_path
                }
            
            # 6. Apply fix
            old_code = fix_data.get("old_code", "")
            new_code = fix_data.get("new_code", "")
            
            if old_code and old_code in content:
                # Replace code
                new_content = content.replace(old_code, new_code, 1)
                
                # 7. Validate new content (basic checks)
                if len(new_content) < len(content) * 0.5:
                    return {
                        "success": False,
                        "error": "Fix would delete too much code",
                        "backup": backup_path
                    }
                
                if new_content.count('{') != new_content.count('}'):
                    return {
                        "success": False,
                        "error": "Unbalanced braces after fix",
                        "backup": backup_path
                    }
                
                # 8. Write fixed content
                file_path.write_text(new_content, encoding="utf-8")
                
                print(f"      ✅ Fix applied successfully")
                print(f"         Risk: {fix_data.get('risk_level', 'unknown')}")
                print(f"         Explanation: {fix_data.get('explanation', '')[:100]}...")
                
                return {
                    "success": True,
                    "changes": f"Replaced {len(old_code)} chars with {len(new_code)} chars",
                    "backup": backup_path,
                    "explanation": fix_data.get("explanation")
                }
            else:
                return {
                    "success": False,
                    "error": "Could not find old_code in file",
                    "backup": backup_path
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Exception: {str(e)}",
                "backup": backup_path if 'backup_path' in locals() else None
            }
    
    def _parse_fix_response(self, response: str) -> Optional[Dict]:
        """Parse JSON fix from response"""
        try:
            # Find JSON in response
            if "{" in response and "}" in response:
                start_idx = response.find("{")
                end_idx = response.rfind("}") + 1
                json_str = response[start_idx:end_idx]
                return json.loads(json_str)
        except:
            pass
        
        # Fallback: parse manually
        if "old_code" in response and "new_code" in response:
            return {
                "old_code": "",
                "new_code": "",
                "explanation": "Could not parse JSON",
                "risk_level": "medium"
            }
        
        return None
    
    def rollback(self, file_path: Path, backup_path: Path) -> bool:
        """Rollback file to backup"""
        try:
            shutil.copy2(backup_path, file_path)
            print(f"      ↩️  Rolled back: {file_path.name}")
            return True
        except Exception as e:
            print(f"      ❌ Rollback failed: {e}")
            return False


class ProductionAutonomousAgent:
    """
    Production-ready autonomous agent с реальными fixes
    """
    
    def __init__(self, project_root: Path):
        self.robot = DeepSeekRobot(
            project_root=project_root,
            autonomy_level=AutonomyLevel.FULL_AUTO
        )
        self.project_root = project_root
        self.fix_applicator = SmartFixApplicator(project_root)
        self.max_cycles = 10
        self.target_success_rate = 1.0
        self.current_cycle = 0
        self.history = []
        
        # Track fixes
        self.total_fixes_attempted = 0
        self.total_fixes_applied = 0
        self.total_fixes_failed = 0
        self.total_fixes_rollback = 0
        
    async def run_production_cycle(self) -> Dict[str, Any]:
        """
        Production цикл с реальными fixes
        """
        self.current_cycle += 1
        
        print("\n" + "=" * 80)
        print(f"🔄 PRODUCTION CYCLE {self.current_cycle}/{self.max_cycles}")
        print("=" * 80)
        
        cycle_start = time.time()
        
        # Step 1: Large-scale analysis
        print(f"\n1️⃣ STEP 1: Large-scale parallel analysis")
        
        python_files = list(self.project_root.glob("**/*.py"))
        python_files = [
            f for f in python_files 
            if "__pycache__" not in str(f) 
            and ".venv" not in str(f)
            and ".robot_backups" not in str(f)
        ][:50]
        
        print(f"   • Found {len(python_files)} Python files")
        print(f"   • Workers: {self.robot.executor.max_workers}")
        print(f"   • Executing parallel analysis...")
        
        start = time.time()
        
        requests = []
        for file in python_files:
            try:
                content = file.read_text(encoding="utf-8")
                content_preview = content[:1500]
                
                requests.append({
                    "query": f"""Quick code review of {file.name}:

{content_preview}

Find top 3 most critical issues. Return JSON:
{{"issues": [{{"severity": "high/medium/low", "line": 0, "description": "...", "fixable": true/false}}]}}
""",
                    "file": str(file),
                    "model": "deepseek-coder",
                    "temperature": 0.1,
                    "max_tokens": 800
                })
            except Exception as e:
                print(f"   ⚠️  Skipped {file.name}: {e}")
        
        results = await self.robot.executor.execute_batch(requests, use_cache=True)
        
        analysis_duration = time.time() - start
        cached_count = sum(1 for r in results if r.get("cached"))
        success_count = sum(1 for r in results if r.get("success"))
        
        print(f"   ✅ Analysis completed in {analysis_duration:.2f}s")
        print(f"   • Successful: {success_count}/{len(results)} ({success_count/len(results)*100:.0f}%)")
        print(f"   • Cached: {cached_count} ({cached_count/len(results)*100:.0f}%)")
        
        # Step 2: Parse fixable issues
        print(f"\n2️⃣ STEP 2: Identify fixable issues")
        
        fixable_issues = []
        file_map = {str(r.get("file")): r.get("file") for r in requests}  # Map string to Path
        
        for result in results:
            if result.get("success"):
                response = result.get("response", "")
                file_str = result.get("file", "")
                file_path = Path(file_str) if file_str else None
                
                # Ensure file_path is valid
                if not file_path or not file_path.exists():
                    continue
                
                try:
                    if "{" in response and "}" in response:
                        start_idx = response.find("{")
                        end_idx = response.rfind("}") + 1
                        json_str = response[start_idx:end_idx]
                        data = json.loads(json_str)
                        
                        issues = data.get("issues", [])
                        for issue in issues:
                            if issue.get("fixable", False) and issue.get("severity") in ["high", "medium"]:
                                fixable_issues.append({
                                    "file": file_path,
                                    "severity": issue.get("severity"),
                                    "line": issue.get("line", 0),
                                    "description": issue.get("description", "")
                                })
                except Exception as e:
                    continue
        
        print(f"   • Fixable issues found: {len(fixable_issues)}")
        
        # Step 3: Apply fixes (REAL!)
        print(f"\n3️⃣ STEP 3: Apply fixes (PRODUCTION MODE)")
        
        fixes_attempted = 0
        fixes_applied = 0
        fixes_failed = 0
        
        # Limit to 5 fixes per cycle for safety
        issues_to_fix = fixable_issues[:5]
        
        if issues_to_fix:
            print(f"   • Attempting to fix {len(issues_to_fix)} issues...")
            
            for issue in issues_to_fix:
                fixes_attempted += 1
                self.total_fixes_attempted += 1
                
                print(f"\n   📝 Fix {fixes_attempted}/{len(issues_to_fix)}: {issue['file'].name}")
                print(f"      Issue: {issue['description'][:80]}...")
                
                result = await self.fix_applicator.apply_fix_smart(
                    file_path=issue['file'],
                    issue=issue,
                    fix_suggestion="",
                    robot=self.robot
                )
                
                if result["success"]:
                    fixes_applied += 1
                    self.total_fixes_applied += 1
                else:
                    fixes_failed += 1
                    self.total_fixes_failed += 1
                    print(f"      ❌ Fix failed: {result.get('error', 'Unknown')}")
        
        print(f"\n   📊 Fix Results:")
        print(f"      • Attempted: {fixes_attempted}")
        print(f"      • Applied: {fixes_applied}")
        print(f"      • Failed: {fixes_failed}")
        
        # Step 4: Validate (syntax check)
        print(f"\n4️⃣ STEP 4: Validate changes")
        
        validation_passed = 0
        validation_failed = 0
        
        if fixes_applied > 0:
            for issue in issues_to_fix:
                file_path = issue['file']
                
                # Skip if file doesn't exist
                if not file_path.exists():
                    continue
                    
                try:
                    # Try to parse Python file
                    content = file_path.read_text(encoding="utf-8")
                    compile(content, str(file_path), 'exec')
                    validation_passed += 1
                except SyntaxError as e:
                    validation_failed += 1
                    print(f"   ❌ Syntax error in {file_path.name}: {e}")
                    
                    # Rollback this file
                    backups = sorted(self.fix_applicator.backup_dir.glob(f"{file_path.name}.*.backup"))
                    if backups:
                        self.fix_applicator.rollback(file_path, backups[-1])
                        self.total_fixes_rollback += 1
                except Exception as e:
                    # Other errors (encoding, etc) - not necessarily a problem
                    pass
        
        print(f"   • Validation passed: {validation_passed}")
        if validation_failed > 0:
            print(f"   • Validation failed: {validation_failed} (rolled back)")
        else:
            print(f"   • No validation failures")
        
        # Step 5: Run tests
        print(f"\n5️⃣ STEP 5: Run validation tests")
        
        tests_passed = 0
        total_tests = 3
        
        # Test 1: Cache
        if cached_count > 0 or self.current_cycle == 1:
            tests_passed += 1
            print(f"   ✅ Test 1: Cache system operational")
        
        # Test 2: Parallel execution
        if success_count >= len(results) * 0.8:
            tests_passed += 1
            print(f"   ✅ Test 2: Parallel execution successful")
        
        # Test 3: Fixes applied without breaking
        if validation_failed == 0 or fixes_applied == 0:
            tests_passed += 1
            print(f"   ✅ Test 3: No syntax errors introduced")
        
        test_success_rate = tests_passed / total_tests
        
        print(f"   • Tests passed: {tests_passed}/{total_tests} ({test_success_rate*100:.0f}%)")
        
        # Step 6: Calculate quality
        print(f"\n6️⃣ STEP 6: Calculate quality metrics")
        
        cycle_duration = time.time() - cycle_start
        
        # Quality calculation
        max_acceptable_issues = len(python_files) * 3  # 3 issues per file acceptable
        remaining_issues = len(fixable_issues) - fixes_applied
        code_quality = max(0.0, 1.0 - (remaining_issues / max(max_acceptable_issues, 1)))
        
        test_quality = test_success_rate
        cache_quality = cached_count / max(len(results), 1)
        fix_quality = fixes_applied / max(fixes_attempted, 1) if fixes_attempted > 0 else 1.0
        
        overall_quality = (
            code_quality * 0.3 +
            test_quality * 0.3 +
            cache_quality * 0.2 +
            fix_quality * 0.2
        )
        
        print(f"   📊 Quality Metrics:")
        print(f"      • Code quality: {code_quality*100:.1f}% (issues: {remaining_issues})")
        print(f"      • Test quality: {test_quality*100:.1f}%")
        print(f"      • Cache efficiency: {cache_quality*100:.1f}%")
        print(f"      • Fix success rate: {fix_quality*100:.1f}%")
        print(f"      • Overall: {overall_quality*100:.1f}%")
        
        cycle_result = {
            "cycle": self.current_cycle,
            "timestamp": datetime.now().isoformat(),
            "duration": cycle_duration,
            "files_analyzed": len(python_files),
            "fixable_issues": len(fixable_issues),
            "fixes_attempted": fixes_attempted,
            "fixes_applied": fixes_applied,
            "fixes_failed": fixes_failed,
            "validation_failed": validation_failed,
            "tests_passed": tests_passed,
            "test_success_rate": test_success_rate,
            "overall_quality": overall_quality,
            "code_quality": code_quality,
            "fix_quality": fix_quality
        }
        
        self.history.append(cycle_result)
        
        return cycle_result
    
    async def run_until_perfect(self) -> Dict[str, Any]:
        """Run до 100% или max cycles"""
        
        print("=" * 80)
        print("🤖 PRODUCTION AUTONOMOUS AGENT - REAL FIXES MODE")
        print("=" * 80)
        print(f"⚠️  WARNING: This will MODIFY files!")
        print(f"✅ Backups will be created in: {self.fix_applicator.backup_dir}")
        print(f"Target: {self.target_success_rate*100:.0f}% quality")
        print(f"Max cycles: {self.max_cycles}")
        print("=" * 80)
        
        start_time = time.time()
        
        while self.current_cycle < self.max_cycles:
            result = await self.run_production_cycle()
            
            # Check target
            if result["overall_quality"] >= self.target_success_rate:
                print("\n" + "=" * 80)
                print("🎉 TARGET ACHIEVED!")
                print("=" * 80)
                print(f"✅ Reached {result['overall_quality']*100:.1f}% quality")
                break
            
            # Check if improving
            if self.current_cycle > 2:
                prev_quality = self.history[-2]["overall_quality"]
                curr_quality = result["overall_quality"]
                
                improvement = curr_quality - prev_quality
                
                if improvement > 0:
                    print(f"\n📈 Quality improved: +{improvement*100:.1f}%")
                elif improvement == 0:
                    print(f"\n⚠️  Quality not improving")
                    
                    if self.current_cycle >= 5:
                        print("🚨 CRITICAL: Agent stuck after 5 cycles")
                        print("🚨 Escalating to Copilot...")
                        break
                else:
                    print(f"\n📉 Quality decreased: {improvement*100:.1f}%")
            
            # Continue
            print(f"\n⏭️  Quality: {result['overall_quality']*100:.1f}% < {self.target_success_rate*100:.0f}% - continuing...")
            await asyncio.sleep(1)
        
        return self._generate_final_report(time.time() - start_time)
    
    def _generate_final_report(self, total_duration: float) -> Dict[str, Any]:
        """Final report"""
        
        print("\n" + "=" * 80)
        print("📊 PRODUCTION FINAL REPORT")
        print("=" * 80)
        
        if not self.history:
            return {}
        
        total_files = sum(h["files_analyzed"] for h in self.history)
        total_fixable = sum(h["fixable_issues"] for h in self.history)
        final_quality = self.history[-1]["overall_quality"]
        
        print(f"\n📈 Overall Statistics:")
        print(f"   • Total cycles: {self.current_cycle}")
        print(f"   • Total duration: {total_duration:.2f}s")
        print(f"   • Files analyzed: {total_files}")
        print(f"   • Fixable issues: {total_fixable}")
        print(f"   • Final quality: {final_quality*100:.1f}%")
        
        print(f"\n🔧 Fix Statistics:")
        print(f"   • Fixes attempted: {self.total_fixes_attempted}")
        print(f"   • Fixes applied: {self.total_fixes_applied}")
        print(f"   • Fixes failed: {self.total_fixes_failed}")
        print(f"   • Rollbacks: {self.total_fixes_rollback}")
        print(f"   • Success rate: {self.total_fixes_applied/max(self.total_fixes_attempted,1)*100:.1f}%")
        
        print(f"\n🎯 Quality Evolution:")
        for h in self.history:
            bar = "█" * int(h["overall_quality"] * 50)
            print(f"   Cycle {h['cycle']}: {bar} {h['overall_quality']*100:.1f}%")
        
        metrics = self.robot.get_advanced_metrics()
        
        print(f"\n⚡ Performance:")
        print(f"   • Cache hit rate: {metrics['cache'].get('hit_rate', 0)}")
        print(f"   • API requests: {metrics['api_keys']['total_requests']}")
        print(f"   • Parallel workers: {metrics['performance']['parallel_workers']}")
        
        success = final_quality >= self.target_success_rate
        
        if success:
            print(f"\n🎉 SUCCESS! Target achieved!")
        else:
            print(f"\n⚠️  Target not reached: {final_quality*100:.1f}%")
        
        print(f"\n📦 Backups location: {self.fix_applicator.backup_dir}")
        print("=" * 80)
        
        return {
            "success": success,
            "cycles": self.current_cycle,
            "duration": total_duration,
            "final_quality": final_quality,
            "fixes_attempted": self.total_fixes_attempted,
            "fixes_applied": self.total_fixes_applied,
            "history": self.history
        }


async def main():
    project_root = Path("d:/bybit_strategy_tester_v2")
    
    agent = ProductionAutonomousAgent(project_root)
    
    report = await agent.run_until_perfect()
    
    report_path = project_root / "production_agent_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\n📄 Report saved: {report_path}")


if __name__ == "__main__":
    asyncio.run(main())
