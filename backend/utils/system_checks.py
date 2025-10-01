"""
System checks and dependency verification utilities.
Ensures all required external dependencies are available before the application starts.
"""

import logging
import subprocess
from typing import Tuple, List, Dict, Any

logger = logging.getLogger(__name__)

class SystemChecker:
    """Check system dependencies and requirements"""

    def __init__(self):
        self.checks_passed = []
        self.checks_failed = []

    def check_ffmpeg(self) -> Tuple[bool, str]:
        """
        Check if ffmpeg is installed and accessible

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                # Extract version information
                version_line = result.stdout.split('\n')[0] if result.stdout else "unknown version"
                message = f"[OK] ffmpeg is available: {version_line}"
                self.checks_passed.append('ffmpeg')
                return True, message
            else:
                message = "[FAIL] ffmpeg command failed to execute"
                self.checks_failed.append('ffmpeg')
                return False, message

        except FileNotFoundError:
            message = (
                "[FAIL] ffmpeg not found. MP3/M4A/AAC audio format support will be unavailable.\n"
                "  Installation instructions:\n"
                "  - Windows: Download from https://www.gyan.dev/ffmpeg/builds/ and add to PATH\n"
                "  - macOS: brew install ffmpeg\n"
                "  - Linux: sudo apt-get install ffmpeg (Ubuntu/Debian) or sudo yum install ffmpeg (RHEL/CentOS)"
            )
            self.checks_failed.append('ffmpeg')
            return False, message

        except subprocess.TimeoutExpired:
            message = "[FAIL] ffmpeg check timed out"
            self.checks_failed.append('ffmpeg')
            return False, message

        except Exception as e:
            message = f"[FAIL] Error checking ffmpeg: {str(e)}"
            self.checks_failed.append('ffmpeg')
            return False, message

    def check_python_version(self, min_version: Tuple[int, int] = (3, 8)) -> Tuple[bool, str]:
        """
        Check if Python version meets minimum requirements

        Args:
            min_version: Minimum required Python version tuple (major, minor)

        Returns:
            Tuple of (success: bool, message: str)
        """
        import sys
        current = (sys.version_info.major, sys.version_info.minor)

        if current >= min_version:
            message = f"[OK] Python {current[0]}.{current[1]} (meets minimum {min_version[0]}.{min_version[1]})"
            self.checks_passed.append('python_version')
            return True, message
        else:
            message = f"[FAIL] Python {current[0]}.{current[1]} (requires {min_version[0]}.{min_version[1]} or higher)"
            self.checks_failed.append('python_version')
            return False, message

    def check_required_packages(self, packages: List[str]) -> Tuple[bool, List[str]]:
        """
        Check if required Python packages are installed

        Args:
            packages: List of package names to check

        Returns:
            Tuple of (all_found: bool, missing_packages: List[str])
        """
        import importlib
        missing = []

        for package in packages:
            try:
                importlib.import_module(package)
            except ImportError:
                missing.append(package)

        if not missing:
            self.checks_passed.append('python_packages')
            return True, []
        else:
            self.checks_failed.append('python_packages')
            return False, missing

    def check_disk_space(self, min_gb: float = 1.0) -> Tuple[bool, str]:
        """
        Check available disk space in temp directory

        Args:
            min_gb: Minimum required free space in GB

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            import shutil
            from config import Config

            # Check disk space in temp folder
            stat = shutil.disk_usage(Config.TEMP_FOLDER)
            free_gb = stat.free / (1024 ** 3)

            if free_gb >= min_gb:
                message = f"[OK] Disk space: {free_gb:.2f} GB available (minimum {min_gb} GB)"
                self.checks_passed.append('disk_space')
                return True, message
            else:
                message = f"[WARN] Disk space: {free_gb:.2f} GB available (recommended minimum {min_gb} GB)"
                # This is a warning, not a failure
                return True, message

        except Exception as e:
            message = f"[WARN] Could not check disk space: {str(e)}"
            return True, message  # Don't fail on this check

    def run_all_checks(self, strict: bool = False) -> Dict[str, Any]:
        """
        Run all system checks

        Args:
            strict: If True, ffmpeg is required. If False, ffmpeg is optional (warning only)

        Returns:
            Dictionary with check results
        """
        results = {
            'all_passed': True,
            'checks': [],
            'summary': {
                'passed': 0,
                'failed': 0,
                'warnings': 0
            }
        }

        # Check Python version
        success, message = self.check_python_version()
        results['checks'].append({'name': 'Python Version', 'passed': success, 'message': message})
        if not success:
            results['all_passed'] = False
            results['summary']['failed'] += 1
        else:
            results['summary']['passed'] += 1

        # Check required packages
        required_packages = ['flask', 'numpy', 'scipy', 'pydub']
        success, missing = self.check_required_packages(required_packages)
        if success:
            message = f"[OK] All required packages installed: {', '.join(required_packages)}"
            results['checks'].append({'name': 'Python Packages', 'passed': True, 'message': message})
            results['summary']['passed'] += 1
        else:
            message = f"[FAIL] Missing packages: {', '.join(missing)}"
            results['checks'].append({'name': 'Python Packages', 'passed': False, 'message': message})
            results['all_passed'] = False
            results['summary']['failed'] += 1

        # Check ffmpeg (optional in non-strict mode)
        success, message = self.check_ffmpeg()
        results['checks'].append({'name': 'ffmpeg', 'passed': success, 'message': message})

        if not success:
            if strict:
                results['all_passed'] = False
                results['summary']['failed'] += 1
            else:
                results['summary']['warnings'] += 1
                # Add note about limited functionality
                results['checks'][-1]['message'] += "\n  Note: Application will start but only WAV files will be supported."
        else:
            results['summary']['passed'] += 1

        # Check disk space
        success, message = self.check_disk_space()
        results['checks'].append({'name': 'Disk Space', 'passed': success, 'message': message})
        if success:
            results['summary']['passed'] += 1

        return results

    def print_results(self, results: Dict[str, Any]) -> None:
        """
        Pretty print check results

        Args:
            results: Results dictionary from run_all_checks()
        """
        print("\n" + "="*60)
        print("  System Dependency Check")
        print("="*60)

        for check in results['checks']:
            print(f"\n{check['message']}")

        print("\n" + "="*60)
        print(f"Summary: {results['summary']['passed']} passed, "
              f"{results['summary']['failed']} failed, "
              f"{results['summary']['warnings']} warnings")
        print("="*60 + "\n")


# Global system checker instance
_system_checker = None

def get_system_checker() -> SystemChecker:
    """Get or create the global system checker instance"""
    global _system_checker
    if _system_checker is None:
        _system_checker = SystemChecker()
    return _system_checker


def run_startup_checks(strict: bool = False, print_output: bool = True) -> bool:
    """
    Run all startup checks

    Args:
        strict: If True, all checks must pass. If False, some checks are warnings only
        print_output: If True, print results to console

    Returns:
        True if all required checks passed, False otherwise
    """
    checker = get_system_checker()
    results = checker.run_all_checks(strict=strict)

    if print_output:
        checker.print_results(results)

    # Log results
    if results['all_passed']:
        logger.info("All system checks passed")
    else:
        logger.warning(f"System checks failed: {results['summary']['failed']} failures")

    return results['all_passed']
