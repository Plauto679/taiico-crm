import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zoneinfo import ZoneInfo
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.renewal_portfolio_report import build_report, report_html, report_csv, traffic_light, window_start, semaphore_summary_html
from services.automatic_mails import default_automations, schedule_matches
from jobs import send_renewal_portfolio_report as job

TODAY = date(2026, 11, 9)

def row(days, number='123', code='16190', status=''):
    return dict(policy_number=number, deadline=(TODAY+timedelta(days=days)).isoformat(), client='<Cliente>', agent_code=code, agent_name='Agente', status='not_started', renewal_status=status)

class RenewalPortfolioReportTests(unittest.TestCase):
    def test_boundaries_include_overdue_and_ten(self):
        self.assertEqual([traffic_light(d) for d in [-400, -1, 0, 9, 10, 11, 30, 31, 45, 46]], ['rojo']*5+['amarillo']*2+['verde']*2+[None])

    def test_three_calendar_months_cutoff(self):
        self.assertEqual(window_start(TODAY),date(2026,8,9))
        self.assertEqual(window_start(date(2026,5,31)),date(2026,2,28))
        rows=[row(-92,'inside'),row(-93,'outside')]
        self.assertEqual([r['policy_number'] for r in build_report(rows,TODAY)['policies']],['inside'])

    def test_scope_statuses_and_period_deduplication(self):
        rows = [row(10),row(10),row(11,'sent',status='Enviado Automáticamente'), row(0,'manual',status='Revision Manual Necesaria'), row(30,'renewed',status='Renovado Automático'),row(31,'cancel',status='Cancelada'),row(45,'other','99999'),row(46,'outside'),row(-90,'old'),row(-365,'123',status='Renovada')]
        report = build_report(rows,TODAY)
        self.assertEqual(report['count'],3)
        self.assertEqual(report['counts'],dict(rojo=3,amarillo=0,verde=0))
        self.assertEqual(report['overdue_count'],1)
        self.assertIn('&lt;Cliente&gt;',report_html(report))
        self.assertIn('<Cliente>',report_csv(report).decode('utf-8-sig'))

    def test_sent_statuses_excluded_but_pending_remains(self):
        sent = ['Enviada Manual', 'Enviado Automáticamente', 'Enviado al cliente', 'Enviado a cliente', 'Enviado al agente', 'Enviado', ' ENVIADA AUTOMÁTICAMENTE ']
        rows = [row(5,str(i),status=status) for i,status in enumerate(sent)]
        rows += [row(5,'pending',status='No enviado'), row(15,'review',status='Revision Manual Necesaria'), row(35,'blank')]
        report = build_report(rows,TODAY)
        self.assertEqual({r['policy_number'] for r in report['policies']}, {'pending','review','blank'})
        for color in ('🔴','🟡','🟢'):
            self.assertIn(color,report_html(report))
        self.assertEqual(report['counts'],dict(rojo=1,amarillo=1,verde=1))

    def test_sent_duplicate_excludes_same_period_only(self):
        report=build_report([row(10,'same'),row(10,'same',status='Enviada Manual'),row(30,'same')],TODAY)
        self.assertEqual([r['days'] for r in report['policies']],[30])

    def test_condensed_semaphore_matches_pending_report_layout(self):
        report=build_report([row(5,'red'),row(15,'yellow'),row(35,'green')],TODAY)
        summary=semaphore_summary_html(report)
        self.assertEqual(summary.count('<td '),3)
        self.assertLess(summary.index('Verde ('),summary.index('Amarillo ('))
        self.assertLess(summary.index('Amarillo ('),summary.index('Rojo ('))
        for background in ('#dcfce7','#fef9c3','#fee2e2'):
            self.assertIn(background,summary)
        self.assertLess(report_html(report).index('Semáforo condensado'),report_html(report).index('🔴 Rojo'))

    def test_schedule_monday_noon_mexico(self):
        config=default_automations()['renewal_portfolio_weekly']
        for day,hour,minute,expected in [(9,11,59,False),(9,12,0,True),(10,12,0,False),(16,12,0,True)]:
            self.assertEqual(schedule_matches(config,datetime(2026,11,day,hour,minute,tzinfo=ZoneInfo(config['timezone']))),expected)
        self.assertEqual(len(config['recipients']),4)

    def test_job_sends_once_and_retains_snapshot(self):
        with TemporaryDirectory() as root, patch.object(job,'REPOSITORY_ROOT',Path(root)), patch.object(job,'local_now_for',return_value=datetime(2026,11,9,12,tzinfo=ZoneInfo('America/Mexico_City'))), patch.object(job,'automation_config',return_value=default_automations()['renewal_portfolio_weekly']), patch.object(job,'load_report',return_value=build_report([row(10)],TODAY)), patch.object(job,'deliver_report') as send:
            job.run(dry_run=True);send.assert_not_called()
            job.run();job.run();self.assertEqual(send.call_count,1)
            self.assertTrue((Path(root)/'.runtime/renewal-portfolio-reports/2026-W46.json').exists())

    def test_ambiguous_delivery_not_retried(self):
        with TemporaryDirectory() as root, patch.object(job,'REPOSITORY_ROOT',Path(root)), patch.object(job,'local_now_for',return_value=datetime(2026,11,9,12,tzinfo=ZoneInfo('America/Mexico_City'))), patch.object(job,'automation_config',return_value=default_automations()['renewal_portfolio_weekly']), patch.object(job,'load_report',return_value=build_report([],TODAY)), patch.object(job,'deliver_report',side_effect=RuntimeError('timeout')) as send:
            with self.assertRaises(RuntimeError):job.run()
            job.run();self.assertEqual(send.call_count,1)

if __name__=='__main__':unittest.main()
