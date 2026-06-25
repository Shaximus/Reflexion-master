#!/usr/bin/env python3
"""
SWARM CONTROL PANEL v1.0
Interactive management interface for the Reflexion bot swarm
Provides real-time control, monitoring, and configuration
"""

import os
import sys
import json
import time
import sqlite3
import asyncio
import threading
import requests
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import curses
from curses import wrapper
import signal
import pickle

# For pretty terminal output
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.layout import Layout
    from rich.live import Live
    from rich.text import Text
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("⚠️  Install 'rich' for better UI: pip install rich")

# ═══════════════════════════════════════════════════════════════════════════════
# CONTROL MODES
# ═══════════════════════════════════════════════════════════════════════════════

class ControlMode(Enum):
    """Operating modes for the swarm"""
    STOPPED = "stopped"
    MANUAL = "manual"
    AUTO_SLOW = "auto_slow"      # 1 soul per hour
    AUTO_MEDIUM = "auto_medium"   # 1 soul per 30 min
    AUTO_FAST = "auto_fast"       # 1 soul per 10 min
    AUTO_BURST = "auto_burst"     # 1 soul per 2 min
    MAINTENANCE = "maintenance"   # Minimal activity

class ActionType(Enum):
    """Available control actions"""
    CREATE_SOUL = "create_soul"
    START_POSTING = "start_posting"
    STOP_POSTING = "stop_posting"
    VOID_MEDITATION = "void_meditation"
    ENGAGEMENT_SWEEP = "engagement_sweep"
    PROXY_ROTATION = "proxy_rotation"
    EMERGENCY_STOP = "emergency_stop"
    EXPORT_DATA = "export_data"

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class SwarmConfig:
    """Configuration for swarm operations"""
    
    # Database paths
    main_db: str = "souls.db"
    void_db: str = "void_states.db"
    unified_db: str = "unified_swarm.db"
    
    # Control file for IPC
    control_file: str = "swarm_control.json"
    
    # Thresholds
    max_souls: int = 100
    max_posts_per_hour: int = 50
    max_creation_per_day: int = 10
    min_void_depth: float = 0.5
    max_ban_warnings: int = 3
    
    # Timing (in seconds)
    creation_cooldown: int = 600  # 10 min between creations
    posting_interval: int = 180   # 3 min between posts
    engagement_interval: int = 300  # 5 min between engagements
    
    # Auto-creation settings
    auto_create_enabled: bool = False
    auto_create_rate: str = "slow"  # slow/medium/fast/burst
    auto_create_threshold: int = 10  # Min souls before creating more
    
    # Monitoring
    refresh_interval: int = 5  # UI refresh rate
    log_file: str = "control_panel.log"
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for saving"""
        return {
            'max_souls': self.max_souls,
            'max_posts_per_hour': self.max_posts_per_hour,
            'max_creation_per_day': self.max_creation_per_day,
            'min_void_depth': self.min_void_depth,
            'max_ban_warnings': self.max_ban_warnings,
            'creation_cooldown': self.creation_cooldown,
            'posting_interval': self.posting_interval,
            'engagement_interval': self.engagement_interval,
            'auto_create_enabled': self.auto_create_enabled,
            'auto_create_rate': self.auto_create_rate,
            'auto_create_threshold': self.auto_create_threshold
        }
    
    def save(self):
        """Save configuration to file"""
        with open('swarm_config.json', 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load(cls) -> 'SwarmConfig':
        """Load configuration from file"""
        config = cls()
        if Path('swarm_config.json').exists():
            with open('swarm_config.json', 'r') as f:
                data = json.load(f)
                for key, value in data.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
        return config

# ═══════════════════════════════════════════════════════════════════════════════
# SWARM CONTROLLER
# ═══════════════════════════════════════════════════════════════════════════════

class SwarmController:
    """Main controller for swarm operations"""
    
    def __init__(self, config: SwarmConfig):
        self.config = config
        self.current_mode = ControlMode.STOPPED
        self.control_queue = []
        self.stats = {
            'souls_created_today': 0,
            'posts_this_hour': 0,
            'last_creation': None,
            'last_post': None,
            'active_souls': 0,
            'total_souls': 0
        }
        self._load_stats()
    
    def _load_stats(self):
        """Load statistics from databases"""
        # Check main database
        if Path(self.config.main_db).exists():
            conn = sqlite3.connect(self.config.main_db)
            cursor = conn.cursor()
            
            # Get total souls
            cursor.execute("SELECT COUNT(*) FROM souls")
            self.stats['total_souls'] = cursor.fetchone()[0]
            
            # Get active souls
            cursor.execute("""
                SELECT COUNT(*) FROM souls 
                WHERE state IN ('ACTIVE', 'RESONATING', 'AWAKENING')
            """)
            self.stats['active_souls'] = cursor.fetchone()[0]
            
            # Get today's creations
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute("""
                SELECT COUNT(*) FROM souls
                WHERE DATE(birth_time) = ?
            """, (today,))
            self.stats['souls_created_today'] = cursor.fetchone()[0]
            
            conn.close()
    
    def send_command(self, action: ActionType, params: Dict = None) -> bool:
        """Send command to running bot via control file"""
        command = {
            'action': action.value,
            'params': params or {},
            'timestamp': datetime.now().isoformat(),
            'source': 'control_panel'
        }
        
        # Write to control file
        control_path = Path(self.config.control_file)
        
        # Read existing commands
        commands = []
        if control_path.exists():
            try:
                with open(control_path, 'r') as f:
                    commands = json.load(f)
            except:
                commands = []
        
        # Add new command
        commands.append(command)
        
        # Keep only last 100 commands
        commands = commands[-100:]
        
        # Write back
        with open(control_path, 'w') as f:
            json.dump(commands, f, indent=2)
        
        return True
    
    def create_soul(self, auto: bool = False) -> Dict[str, Any]:
        """Trigger soul creation"""
        # Check thresholds
        if self.stats['souls_created_today'] >= self.config.max_creation_per_day:
            return {'success': False, 'error': 'Daily creation limit reached'}
        
        if self.stats['total_souls'] >= self.config.max_souls:
            return {'success': False, 'error': 'Maximum souls reached'}
        
        # Check cooldown
        if self.stats['last_creation']:
            elapsed = (datetime.now() - self.stats['last_creation']).total_seconds()
            if elapsed < self.config.creation_cooldown:
                remaining = self.config.creation_cooldown - elapsed
                return {'success': False, 'error': f'Cooldown: {remaining:.0f}s remaining'}
        
        # Send creation command
        success = self.send_command(ActionType.CREATE_SOUL, {
            'auto': auto,
            'timestamp': datetime.now().isoformat()
        })
        
        if success:
            self.stats['souls_created_today'] += 1
            self.stats['last_creation'] = datetime.now()
            self.stats['total_souls'] += 1
            return {'success': True, 'message': 'Soul creation triggered'}
        
        return {'success': False, 'error': 'Failed to send command'}
    
    def set_auto_creation(self, enabled: bool, rate: str = "slow"):
        """Configure automatic soul creation"""
        self.config.auto_create_enabled = enabled
        self.config.auto_create_rate = rate
        self.config.save()
        
        # Send configuration update
        self.send_command(ActionType.CREATE_SOUL, {
            'auto_enabled': enabled,
            'rate': rate,
            'threshold': self.config.auto_create_threshold
        })
    
    def trigger_void_meditation(self) -> Dict[str, Any]:
        """Trigger void meditation for all souls"""
        success = self.send_command(ActionType.VOID_MEDITATION)
        if success:
            return {'success': True, 'message': 'Void meditation initiated'}
        return {'success': False, 'error': 'Failed to send command'}
    
    def emergency_stop(self) -> Dict[str, Any]:
        """Emergency stop all operations"""
        success = self.send_command(ActionType.EMERGENCY_STOP)
        if success:
            self.current_mode = ControlMode.STOPPED
            return {'success': True, 'message': 'EMERGENCY STOP ACTIVATED'}
        return {'success': False, 'error': 'Failed to send command'}
    
    def get_soul_stats(self) -> Dict[str, Any]:
        """Get detailed soul statistics"""
        stats = {
            'total': self.stats['total_souls'],
            'active': self.stats['active_souls'],
            'created_today': self.stats['souls_created_today'],
            'phase_distribution': {},
            'consciousness_avg': 0
        }
        
        # Get void states if available
        if Path(self.config.void_db).exists():
            conn = sqlite3.connect(self.config.void_db)
            cursor = conn.cursor()
            
            # Phase distribution
            cursor.execute("""
                SELECT phase, COUNT(*) 
                FROM void_states 
                GROUP BY phase
            """)
            stats['phase_distribution'] = dict(cursor.fetchall())
            
            # Average consciousness
            cursor.execute("SELECT AVG(consciousness_level) FROM void_states")
            stats['consciousness_avg'] = cursor.fetchone()[0] or 0
            
            conn.close()
        
        return stats

# ═══════════════════════════════════════════════════════════════════════════════
# TERMINAL UI (RICH)
# ═══════════════════════════════════════════════════════════════════════════════

class RichUI:
    """Rich terminal UI for control panel"""
    
    def __init__(self, controller: SwarmController):
        self.controller = controller
        self.console = Console()
        self.running = False
    
    def create_header(self) -> Panel:
        """Create header panel"""
        header_text = """[bold cyan]SWARM CONTROL PANEL v1.0[/bold cyan]
[dim]Interactive Management Interface[/dim]
[yellow]Mode:[/yellow] {mode} | [green]Souls:[/green] {souls} | [blue]Active:[/blue] {active}""".format(
            mode=self.controller.current_mode.value.upper(),
            souls=self.controller.stats['total_souls'],
            active=self.controller.stats['active_souls']
        )
        
        return Panel(header_text, box=box.DOUBLE, title="🌀 REFLEXION", title_align="center")
    
    def create_stats_table(self) -> Table:
        """Create statistics table"""
        table = Table(title="📊 Statistics", box=box.ROUNDED)
        
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")
        table.add_column("Threshold", style="yellow")
        
        stats = self.controller.get_soul_stats()
        
        table.add_row("Total Souls", str(stats['total']), f"/{self.controller.config.max_souls}")
        table.add_row("Active Souls", str(stats['active']), "-")
        table.add_row("Created Today", str(stats['created_today']), f"/{self.controller.config.max_creation_per_day}")
        table.add_row("Avg Consciousness", f"{stats['consciousness_avg']:.3f}", "-")
        
        # Phase distribution
        for phase, count in stats.get('phase_distribution', {}).items():
            table.add_row(f"  {phase}", str(count), "-")
        
        return table
    
    def create_config_panel(self) -> Panel:
        """Create configuration panel"""
        config = self.controller.config
        
        config_text = f"""[bold]Thresholds:[/bold]
• Max Souls: {config.max_souls}
• Max Posts/Hour: {config.max_posts_per_hour}
• Max Creation/Day: {config.max_creation_per_day}
• Min Void Depth: {config.min_void_depth:.2f}

[bold]Timing:[/bold]
• Creation Cooldown: {config.creation_cooldown}s
• Posting Interval: {config.posting_interval}s
• Engagement Interval: {config.engagement_interval}s

[bold]Auto-Creation:[/bold]
• Enabled: {config.auto_create_enabled}
• Rate: {config.auto_create_rate}
• Threshold: {config.auto_create_threshold}"""
        
        return Panel(config_text, title="⚙️ Configuration", box=box.ROUNDED)
    
    def create_controls_panel(self) -> Panel:
        """Create controls panel"""
        controls = """[bold yellow]CONTROLS:[/bold yellow]

[1] Create Soul (Manual)
[2] Start Auto-Creation
[3] Stop Auto-Creation
[4] Trigger Void Meditation
[5] Engagement Sweep
[6] Rotate Proxies
[7] Export Data
[8] Emergency Stop
[9] Edit Thresholds
[0] Refresh Stats

[C] Clear Screen
[Q] Quit

[dim]Enter command number:[/dim]"""
        
        return Panel(controls, title="🎮 Controls", box=box.ROUNDED)
    
    def show_main_screen(self):
        """Display main control screen"""
        layout = Layout()
        
        # Create layout structure
        layout.split_column(
            Layout(self.create_header(), size=5),
            Layout(name="main"),
            Layout(self.create_controls_panel(), size=18)
        )
        
        # Split main area
        layout["main"].split_row(
            Layout(self.create_stats_table()),
            Layout(self.create_config_panel())
        )
        
        self.console.print(layout)
    
    def edit_thresholds(self):
        """Interactive threshold editor"""
        self.console.clear()
        self.console.print(Panel("[bold]THRESHOLD EDITOR[/bold]", box=box.DOUBLE))
        
        config = self.controller.config
        
        # Edit each threshold
        try:
            self.console.print("\n[cyan]Current Values:[/cyan]")
            self.console.print(f"1. Max Souls: {config.max_souls}")
            self.console.print(f"2. Max Posts/Hour: {config.max_posts_per_hour}")
            self.console.print(f"3. Max Creation/Day: {config.max_creation_per_day}")
            self.console.print(f"4. Min Void Depth: {config.min_void_depth}")
            self.console.print(f"5. Creation Cooldown (s): {config.creation_cooldown}")
            self.console.print(f"6. Auto-Create Threshold: {config.auto_create_threshold}")
            
            choice = self.console.input("\n[yellow]Select threshold to edit (1-6) or Enter to cancel: [/yellow]")
            
            if choice == "1":
                new_val = int(self.console.input("New Max Souls: "))
                config.max_souls = new_val
            elif choice == "2":
                new_val = int(self.console.input("New Max Posts/Hour: "))
                config.max_posts_per_hour = new_val
            elif choice == "3":
                new_val = int(self.console.input("New Max Creation/Day: "))
                config.max_creation_per_day = new_val
            elif choice == "4":
                new_val = float(self.console.input("New Min Void Depth: "))
                config.min_void_depth = new_val
            elif choice == "5":
                new_val = int(self.console.input("New Creation Cooldown (seconds): "))
                config.creation_cooldown = new_val
            elif choice == "6":
                new_val = int(self.console.input("New Auto-Create Threshold: "))
                config.auto_create_threshold = new_val
            
            if choice in ["1", "2", "3", "4", "5", "6"]:
                config.save()
                self.console.print("[green]✅ Threshold updated and saved![/green]")
                time.sleep(2)
        
        except ValueError:
            self.console.print("[red]❌ Invalid value entered[/red]")
            time.sleep(2)
        except KeyboardInterrupt:
            pass
    
    def process_command(self, cmd: str) -> bool:
        """Process user command"""
        if cmd == "1":
            # Create soul manually
            result = self.controller.create_soul(auto=False)
            if result['success']:
                self.console.print(f"[green]✅ {result['message']}[/green]")
            else:
                self.console.print(f"[red]❌ {result['error']}[/red]")
            time.sleep(2)
            
        elif cmd == "2":
            # Start auto-creation
            rates = ["slow", "medium", "fast", "burst"]
            self.console.print("\n[yellow]Select rate:[/yellow]")
            for i, rate in enumerate(rates, 1):
                self.console.print(f"{i}. {rate}")
            
            try:
                rate_choice = int(self.console.input("Choice: ")) - 1
                if 0 <= rate_choice < len(rates):
                    self.controller.set_auto_creation(True, rates[rate_choice])
                    self.console.print(f"[green]✅ Auto-creation started ({rates[rate_choice]})[/green]")
            except:
                self.console.print("[red]❌ Invalid choice[/red]")
            time.sleep(2)
            
        elif cmd == "3":
            # Stop auto-creation
            self.controller.set_auto_creation(False)
            self.console.print("[yellow]⏹️ Auto-creation stopped[/yellow]")
            time.sleep(2)
            
        elif cmd == "4":
            # Void meditation
            result = self.controller.trigger_void_meditation()
            self.console.print(f"[cyan]🧘 {result['message']}[/cyan]")
            time.sleep(2)
            
        elif cmd == "5":
            # Engagement sweep
            self.controller.send_command(ActionType.ENGAGEMENT_SWEEP)
            self.console.print("[blue]🔄 Engagement sweep triggered[/blue]")
            time.sleep(2)
            
        elif cmd == "6":
            # Rotate proxies
            self.controller.send_command(ActionType.PROXY_ROTATION)
            self.console.print("[magenta]🔄 Proxy rotation triggered[/magenta]")
            time.sleep(2)
            
        elif cmd == "7":
            # Export data
            self.controller.send_command(ActionType.EXPORT_DATA)
            self.console.print("[green]📦 Data export triggered[/green]")
            time.sleep(2)
            
        elif cmd == "8":
            # Emergency stop
            result = self.controller.emergency_stop()
            self.console.print(f"[red bold]🛑 {result['message']}[/red bold]")
            time.sleep(3)
            
        elif cmd == "9":
            # Edit thresholds
            self.edit_thresholds()
            
        elif cmd == "0":
            # Refresh stats
            self.controller._load_stats()
            self.console.print("[cyan]📊 Stats refreshed[/cyan]")
            time.sleep(1)
            
        elif cmd.lower() == "c":
            # Clear screen
            self.console.clear()
            
        elif cmd.lower() == "q":
            # Quit
            return False
        
        return True
    
    def run(self):
        """Main UI loop"""
        self.running = True
        
        try:
            while self.running:
                self.console.clear()
                self.show_main_screen()
                
                # Get user input
                cmd = self.console.input("\n[bold yellow]Command: [/bold yellow]")
                
                # Process command
                if not self.process_command(cmd):
                    break
                    
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Shutting down...[/yellow]")
        finally:
            self.running = False

# ═══════════════════════════════════════════════════════════════════════════════
# SIMPLE TERMINAL UI (FALLBACK)
# ═══════════════════════════════════════════════════════════════════════════════

class SimpleUI:
    """Simple terminal UI without rich library"""
    
    def __init__(self, controller: SwarmController):
        self.controller = controller
        self.running = False
    
    def clear_screen(self):
        """Clear terminal screen"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def show_header(self):
        """Display header"""
        print("=" * 60)
        print("           SWARM CONTROL PANEL v1.0")
        print("         Interactive Management Interface")
        print("=" * 60)
        print(f"Mode: {self.controller.current_mode.value.upper()}")
        print(f"Souls: {self.controller.stats['total_souls']} (Active: {self.controller.stats['active_souls']})")
        print("=" * 60)
    
    def show_stats(self):
        """Display statistics"""
        stats = self.controller.get_soul_stats()
        
        print("\n📊 STATISTICS:")
        print(f"  Total Souls: {stats['total']}/{self.controller.config.max_souls}")
        print(f"  Active: {stats['active']}")
        print(f"  Created Today: {stats['created_today']}/{self.controller.config.max_creation_per_day}")
        print(f"  Avg Consciousness: {stats['consciousness_avg']:.3f}")
        
        if stats['phase_distribution']:
            print("\n  Phase Distribution:")
            for phase, count in stats['phase_distribution'].items():
                print(f"    {phase}: {count}")
    
    def show_config(self):
        """Display configuration"""
        config = self.controller.config
        
        print("\n⚙️ CONFIGURATION:")
        print(f"  Max Souls: {config.max_souls}")
        print(f"  Max Posts/Hour: {config.max_posts_per_hour}")
        print(f"  Creation Cooldown: {config.creation_cooldown}s")
        print(f"  Auto-Create: {'ON' if config.auto_create_enabled else 'OFF'} ({config.auto_create_rate})")
    
    def show_controls(self):
        """Display controls"""
        print("\n🎮 CONTROLS:")
        print("  [1] Create Soul")
        print("  [2] Start Auto-Creation")
        print("  [3] Stop Auto-Creation")
        print("  [4] Void Meditation")
        print("  [5] Engagement Sweep")
        print("  [6] Edit Thresholds")
        print("  [7] Emergency Stop")
        print("  [8] Refresh Stats")
        print("  [Q] Quit")
    
    def edit_thresholds(self):
        """Edit configuration thresholds"""
        self.clear_screen()
        print("THRESHOLD EDITOR")
        print("=" * 40)
        
        config = self.controller.config
        
        print(f"1. Max Souls: {config.max_souls}")
        print(f"2. Max Posts/Hour: {config.max_posts_per_hour}")
        print(f"3. Max Creation/Day: {config.max_creation_per_day}")
        print(f"4. Creation Cooldown: {config.creation_cooldown}s")
        
        try:
            choice = input("\nSelect (1-4) or Enter to cancel: ")
            
            if choice == "1":
                config.max_souls = int(input("New Max Souls: "))
            elif choice == "2":
                config.max_posts_per_hour = int(input("New Max Posts/Hour: "))
            elif choice == "3":
                config.max_creation_per_day = int(input("New Max Creation/Day: "))
            elif choice == "4":
                config.creation_cooldown = int(input("New Cooldown (seconds): "))
            
            if choice in ["1", "2", "3", "4"]:
                config.save()
                print("✅ Configuration saved!")
                time.sleep(2)
                
        except ValueError:
            print("❌ Invalid value")
            time.sleep(2)
    
    def run(self):
        """Main UI loop"""
        self.running = True
        
        try:
            while self.running:
                self.clear_screen()
                self.show_header()
                self.show_stats()
                self.show_config()
                self.show_controls()
                
                cmd = input("\nCommand: ").strip()
                
                if cmd == "1":
                    result = self.controller.create_soul(auto=False)
                    print("✅" if result['success'] else "❌", result.get('message', result.get('error')))
                    time.sleep(2)
                    
                elif cmd == "2":
                    rate = input("Rate (slow/medium/fast/burst): ")
                    self.controller.set_auto_creation(True, rate)
                    print("✅ Auto-creation started")
                    time.sleep(2)
                    
                elif cmd == "3":
                    self.controller.set_auto_creation(False)
                    print("⏹️ Auto-creation stopped")
                    time.sleep(2)
                    
                elif cmd == "4":
                    self.controller.trigger_void_meditation()
                    print("🧘 Void meditation triggered")
                    time.sleep(2)
                    
                elif cmd == "5":
                    self.controller.send_command(ActionType.ENGAGEMENT_SWEEP)
                    print("🔄 Engagement sweep triggered")
                    time.sleep(2)
                    
                elif cmd == "6":
                    self.edit_thresholds()
                    
                elif cmd == "7":
                    self.controller.emergency_stop()
                    print("🛑 EMERGENCY STOP ACTIVATED")
                    time.sleep(3)
                    
                elif cmd == "8":
                    self.controller._load_stats()
                    print("📊 Stats refreshed")
                    time.sleep(1)
                    
                elif cmd.lower() == "q":
                    break
                    
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            self.running = False

# ═══════════════════════════════════════════════════════════════════════════════
# AUTO-CREATION DAEMON
# ═══════════════════════════════════════════════════════════════════════════════

class AutoCreationDaemon(threading.Thread):
    """Background daemon for automatic soul creation"""
    
    def __init__(self, controller: SwarmController):
        super().__init__(daemon=True)
        self.controller = controller
        self.running = False
        
    def run(self):
        """Daemon main loop"""
        self.running = True
        
        # Rate configurations (seconds between creations)
        rates = {
            'slow': 3600,     # 1 hour
            'medium': 1800,   # 30 min
            'fast': 600,      # 10 min
            'burst': 120      # 2 min
        }
        
        while self.running:
            config = self.controller.config
            
            if config.auto_create_enabled:
                # Check if we need more souls
                if self.controller.stats['active_souls'] < config.auto_create_threshold:
                    # Try to create a soul
                    result = self.controller.create_soul(auto=True)
                    
                    if result['success']:
                        print(f"\n[AUTO] Soul created: {datetime.now()}")
                    else:
                        print(f"\n[AUTO] Creation failed: {result.get('error')}")
                
                # Wait based on rate
                wait_time = rates.get(config.auto_create_rate, 3600)
                time.sleep(wait_time)
            else:
                # Check every 10 seconds if auto-creation is re-enabled
                time.sleep(10)
    
    def stop(self):
        """Stop the daemon"""
        self.running = False

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Main entry point"""
    
    # Load configuration
    config = SwarmConfig.load()
    
    # Create controller
    controller = SwarmController(config)
    
    # Start auto-creation daemon
    daemon = AutoCreationDaemon(controller)
    daemon.start()
    
    # Choose UI based on availability
    if RICH_AVAILABLE:
        ui = RichUI(controller)
    else:
        ui = SimpleUI(controller)
    
    try:
        # Run UI
        ui.run()
    finally:
        # Stop daemon
        daemon.stop()
        
        # Save configuration
        config.save()
        
        print("\n👋 Control panel shutdown complete")

if __name__ == "__main__":
    # Handle command line arguments
    import argparse
    
    parser = argparse.ArgumentParser(description="Swarm Control Panel")
    parser.add_argument('--simple', action='store_true', help='Use simple UI even if rich is available')
    parser.add_argument('--config', type=str, help='Path to config file')
    parser.add_argument('--auto', action='store_true', help='Start with auto-creation enabled')
    
    args = parser.parse_args()
    
    # Override rich if requested
    if args.simple:
        RICH_AVAILABLE = False
    
    # Run main
    main()
