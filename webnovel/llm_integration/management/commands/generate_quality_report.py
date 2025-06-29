from django.core.management.base import BaseCommand
from llm_integration.utils import generate_quality_report, aggregate_quality_metrics
from llm_integration.models import LLMServiceCall, LLMProvider
from django.db.models import Count
import json


class Command(BaseCommand):
    help = 'Generate LLM quality control report'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Number of days to analyze (default: 7)'
        )
        parser.add_argument(
            '--format',
            type=str,
            choices=['text', 'json'],
            default='text',
            help='Output format (default: text)'
        )
        parser.add_argument(
            '--aggregate-only',
            action='store_true',
            help='Only aggregate metrics without generating full report'
        )

    def handle(self, *args, **options):
        days = options['days']
        output_format = options['format']
        aggregate_only = options['aggregate_only']
        
        if aggregate_only:
            self.stdout.write(f"Aggregating metrics for the last {days} days...")
            metrics = aggregate_quality_metrics(days, force_recalculate=True)
            self.stdout.write(
                self.style.SUCCESS(f"✓ Aggregated {len(metrics)} metric records")
            )
            return
        
        self.stdout.write(f"Generating quality report for the last {days} days...")
        
        # Generate the report
        report = generate_quality_report(days)
        
        if output_format == 'json':
            # Output as JSON
            self.stdout.write(json.dumps(report, default=str, indent=2))
        else:
            # Output as formatted text
            self._print_text_report(report)

    def _print_text_report(self, report):
        """Print a formatted text report"""
        self.stdout.write("\n" + "="*80)
        self.stdout.write("LLM QUALITY CONTROL REPORT")
        self.stdout.write("="*80)
        
        # Period information
        period = report['period']
        self.stdout.write(f"\n📅 Period: {period['start'].strftime('%Y-%m-%d %H:%M')} to {period['end'].strftime('%Y-%m-%d %H:%M')} ({period['days']} days)")
        
        # Overall statistics
        self.stdout.write(f"\n📊 Overall Statistics:")
        self.stdout.write(f"   Total API Calls: {report['total_calls']:,}")
        self.stdout.write(f"   Total Cost: ${report['total_cost']:.4f}")
        
        # Provider summary
        self.stdout.write(f"\n🏢 Provider Performance Summary:")
        self.stdout.write("-" * 60)
        
        if not report['provider_summary']:
            self.stdout.write("   No provider data available for this period")
        else:
            for provider_name, data in report['provider_summary'].items():
                status_icon = "✓" if data['api_key_configured'] else "✗"
                success_rate_pct = data['success_rate'] * 100
                avg_response_sec = data['avg_response_time_ms'] / 1000
                
                self.stdout.write(f"   {status_icon} {data['display_name']} ({provider_name})")
                self.stdout.write(f"      Calls: {data['total_calls']:,} | Success Rate: {success_rate_pct:.1f}% | Avg Response: {avg_response_sec:.2f}s")
                self.stdout.write(f"      Cost: ${data['total_cost']:.4f} | Tokens: {data['total_tokens']:,}")
                self.stdout.write()
        
        # Operation metrics
        self.stdout.write(f"\n🔧 Operation Performance:")
        self.stdout.write("-" * 60)
        
        if not report['operation_metrics']:
            self.stdout.write("   No operation data available for this period")
        else:
            for op_metric in report['operation_metrics']:
                operation = op_metric['operation'].replace('_', ' ').title()
                success_rate_pct = op_metric['avg_success_rate'] * 100
                avg_response_sec = op_metric['avg_response_time'] / 1000
                
                self.stdout.write(f"   📝 {operation}")
                self.stdout.write(f"      Calls: {op_metric['total_calls']:,} | Success Rate: {success_rate_pct:.1f}% | Avg Response: {avg_response_sec:.2f}s")
                self.stdout.write(f"      Cost: ${op_metric['total_cost']:.4f}")
                self.stdout.write()
        
        # Recent errors
        self.stdout.write(f"\n❌ Recent Errors (Last 10):")
        self.stdout.write("-" * 60)
        
        if not report['recent_errors']:
            self.stdout.write("   No errors recorded in this period")
        else:
            for error in report['recent_errors']:
                error_date = error['created_at'].strftime('%Y-%m-%d %H:%M')
                self.stdout.write(f"   🚨 {error_date} | {error['provider']} ({error['model']})")
                self.stdout.write(f"      Operation: {error['operation']} | Status: {error['status']}")
                self.stdout.write(f"      Error: {error['error_message']}")
                self.stdout.write()
        
        # Recommendations
        self.stdout.write(f"\n💡 Recommendations:")
        self.stdout.write("-" * 60)
        
        if report['provider_summary']:
            # Find best performing provider
            best_provider = max(
                report['provider_summary'].items(),
                key=lambda x: x[1]['success_rate']
            )
            
            worst_provider = min(
                report['provider_summary'].items(),
                key=lambda x: x[1]['success_rate']
            )
            
            if best_provider[1]['success_rate'] > 0.95:
                self.stdout.write(f"   ✅ {best_provider[1]['display_name']} is performing excellently ({best_provider[1]['success_rate']*100:.1f}% success rate)")
            
            if worst_provider[1]['success_rate'] < 0.8:
                self.stdout.write(f"   ⚠️  {worst_provider[1]['display_name']} needs attention ({worst_provider[1]['success_rate']*100:.1f}% success rate)")
            
            # Cost optimization
            most_expensive = max(
                report['provider_summary'].items(),
                key=lambda x: x[1]['total_cost']
            )
            
            if most_expensive[1]['total_cost'] > 1.0:  # More than $1
                self.stdout.write(f"   💰 {most_expensive[1]['display_name']} is the most expensive (${most_expensive[1]['total_cost']:.4f})")
        
        if report['recent_errors']:
            error_count = len(report['recent_errors'])
            self.stdout.write(f"   🔍 {error_count} errors detected - review error patterns and consider provider fallbacks")
        
        self.stdout.write("\n" + "="*80)
        self.stdout.write("Report generated successfully!")
        self.stdout.write("="*80) 