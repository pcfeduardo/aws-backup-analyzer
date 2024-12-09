#!/usr/bin/env python3
import boto3
from datetime import datetime, timedelta
from typing import Dict, List, Set
import json
import pandas as pd
from collections import defaultdict

def get_available_regions() -> List[str]:
    """Retorna lista de regiões AWS disponíveis para o serviço AWS Backup."""
    try:
        session = boto3.Session()
        return session.get_available_regions('backup')
    except Exception as e:
        print(f"Erro ao obter regiões disponíveis: {str(e)}")
        return []

def prompt_region_selection() -> str:
    """Solicita ao usuário que selecione uma região AWS válida."""
    available_regions = get_available_regions()
    
    print("\nRegiões AWS disponíveis:")
    for i, region in enumerate(available_regions, 1):
        print(f"{i}. {region}")
    
    while True:
        try:
            choice = input("\nEscolha o número da região ou digite o nome da região diretamente: ").strip()
            
            # Verifica se o usuário digitou um número
            if choice.isdigit():
                index = int(choice) - 1
                if 0 <= index < len(available_regions):
                    return available_regions[index]
            # Verifica se o usuário digitou o nome da região
            elif choice in available_regions:
                return choice
                
            print("Escolha inválida. Por favor, selecione uma região válida.")
        except ValueError:
            print("Entrada inválida. Por favor, digite um número ou nome de região válido.")

class AWSBackupAnalyzer:
    def __init__(self, region: str):
        self.region = region
        self.backup_client = boto3.client('backup', region_name=region)
        self.ec2_client = boto3.client('ec2', region_name=region)
        
    def get_ebs_volumes(self) -> List[Dict]:
        """Obtém informações sobre volumes EBS."""
        try:
            ec2 = boto3.client('ec2', region_name=self.region)
            volumes = []
            paginator = ec2.get_paginator('describe_volumes')
            
            for page in paginator.paginate():
                for volume in page['Volumes']:
                    volume_info = {
                        'volume_id': volume['VolumeId'],
                        'size_gb': volume['Size'],
                        'volume_type': volume['VolumeType'],
                        'state': volume['State'],
                        'creation_date': volume['CreateTime'].strftime('%Y-%m-%d %H:%M'),
                        'encrypted': volume.get('Encrypted', False),
                        'availability_zone': volume['AvailabilityZone'],
                        'attached_instance': 'Not Attached',
                        'device': 'N/A'
                    }
                    
                    if volume['Attachments']:
                        attachment = volume['Attachments'][0]
                        volume_info.update({
                            'attached_instance': attachment['InstanceId'],
                            'device': attachment['Device']
                        })
                    
                    # Obter tags se existirem
                    volume_info['name'] = next(
                        (tag['Value'] for tag in volume.get('Tags', []) if tag['Key'] == 'Name'),
                        'N/A'
                    )
                    
                    volumes.append(volume_info)
            
            return volumes
        except Exception as e:
            print(f"Erro ao obter volumes EBS: {str(e)}")
            return []

    def get_snapshots(self) -> List[Dict]:
        """Obtém informações sobre snapshots EC2."""
        try:
            ec2 = boto3.client('ec2', region_name=self.region)
            snapshots = []
            paginator = ec2.get_paginator('describe_snapshots')
            
            for page in paginator.paginate(OwnerIds=['self']):
                for snapshot in page['Snapshots']:
                    snapshot_info = {
                        'snapshot_id': snapshot['SnapshotId'],
                        'volume_id': snapshot.get('VolumeId', 'N/A'),
                        'start_time': snapshot['StartTime'].strftime('%Y-%m-%d %H:%M'),
                        'size_gb': snapshot['VolumeSize'],
                        'state': snapshot['State'],
                        'progress': snapshot['Progress'],
                        'description': snapshot.get('Description', 'N/A'),
                        'encrypted': snapshot.get('Encrypted', False)
                    }
                    
                    # Obter tags se existirem
                    snapshot_info['name'] = next(
                        (tag['Value'] for tag in snapshot.get('Tags', []) if tag['Key'] == 'Name'),
                        'N/A'
                    )
                    
                    snapshots.append(snapshot_info)
            
            return snapshots
        except Exception as e:
            print(f"Erro ao obter snapshots: {str(e)}")
            return []
    
    def get_backup_jobs(self, days: int = 90) -> List[Dict]:
        """Obtém jobs de backup executados nos últimos dias especificados."""
        try:
            start_date = datetime.now() - timedelta(days=days)
            jobs = []
            
            # Lista para todos os estados possíveis
            states = ['COMPLETED', 'FAILED', 'EXPIRED', 'PARTIAL']
            
            for state in states:
                paginator = self.backup_client.get_paginator('list_backup_jobs')
                for page in paginator.paginate(
                    ByCreatedAfter=start_date.isoformat(),
                    ByState=state
                ):
                    jobs.extend(page['BackupJobs'])
            
            return jobs
        except Exception as e:
            print(f"Erro ao obter jobs de backup: {str(e)}")
            return []

    def get_backup_plans(self) -> List[Dict]:
        """Obtém todos os planos de backup e suas configurações."""
        try:
            plans = []
            paginator = self.backup_client.get_paginator('list_backup_plans')
            
            for page in paginator.paginate():
                for plan in page['BackupPlansList']:
                    plan_details = self.backup_client.get_backup_plan(
                        BackupPlanId=plan['BackupPlanId']
                    )
                    
                    selections = []
                    try:
                        selection_paginator = self.backup_client.get_paginator('list_backup_selections')
                        for sel_page in selection_paginator.paginate(BackupPlanId=plan['BackupPlanId']):
                            for selection in sel_page['BackupSelectionsList']:
                                sel_details = self.backup_client.get_backup_selection(
                                    BackupPlanId=plan['BackupPlanId'],
                                    SelectionId=selection['SelectionId']
                                )
                                selections.append({
                                    'selection_name': sel_details['BackupSelection'].get('SelectionName', 'N/A'),
                                    'iam_role_arn': sel_details['BackupSelection'].get('IamRoleArn', 'N/A'),
                                    'resources': sel_details['BackupSelection'].get('Resources', []),
                                    'conditions': sel_details['BackupSelection'].get('Conditions', {})
                                })
                    except Exception as e:
                        print(f"Erro ao obter seleções para plano {plan['BackupPlanId']}: {str(e)}")

                    plans.append({
                        'plan_id': plan['BackupPlanId'],
                        'plan_name': plan.get('BackupPlanName', 'N/A'),
                        'version_id': plan.get('VersionId', 'N/A'),
                        'creation_date': plan['CreationDate'].strftime('%Y-%m-%d %H:%M'),
                        'deployment_status': plan.get('DeploymentStatus', 'N/A'),
                        'rules': [{
                            'rule_name': rule.get('RuleName', 'N/A'),
                            'target_vault_name': rule.get('TargetBackupVaultName', 'N/A'),
                            'schedule_expression': rule.get('ScheduleExpression', 'N/A'),
                            'start_window_minutes': rule.get('StartWindowMinutes', 'N/A'),
                            'completion_window_minutes': rule.get('CompletionWindowMinutes', 'N/A'),
                            'lifecycle': rule.get('Lifecycle', {}),
                            'enable_continuous_backup': rule.get('EnableContinuousBackup', False)
                        } for rule in plan_details['BackupPlan'].get('Rules', [])],
                        'selections': selections
                    })
            
            return plans
        except Exception as e:
            print(f"Erro ao obter planos de backup: {str(e)}")
            return []

    def get_unique_resources(self, jobs: List[Dict]) -> List[Dict]:
        """Obtém lista de recursos únicos dos backups."""
        unique_resources = {}
        
        for job in jobs:
            resource_id = job['ResourceArn'].split('/')[-1]
            if resource_id not in unique_resources:
                unique_resources[resource_id] = {
                    'resource_id': resource_id,
                    'resource_type': job.get('ResourceType', 'N/A'),
                    'resource_arn': job['ResourceArn'],
                    'last_backup': job['CreationDate'].strftime('%Y-%m-%d %H:%M'),
                    'backup_vault': job.get('BackupVaultName', 'N/A')
                }
        
        return list(unique_resources.values())

    def get_job_status_summary(self, jobs: List[Dict]) -> Dict:
        """Retorna sumário dos status dos jobs."""
        status_summary = defaultdict(int)
        
        for job in jobs:
            state = job['State']
            if state == 'COMPLETED' and job.get('StatusMessage', '').lower().find('issue') != -1:
                status_summary['COMPLETED_WITH_ISSUES'] += 1
            else:
                status_summary[state] += 1
        
        return dict(status_summary)

    def generate_backup_report(self, days: int = 90) -> Dict:
        """Gera relatório detalhado dos backups."""
        jobs = self.get_backup_jobs(days)
        plans = self.get_backup_plans()
        unique_resources = self.get_unique_resources(jobs)
        job_status = self.get_job_status_summary(jobs)
        
        report = {
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'region': self.region,
            'period_days': days,
            'total_backups': len(jobs),
            'job_status_summary': job_status,
            'plans': plans,
            'unique_resources': unique_resources,
            'backups': [{
                'backup_job_id': job.get('BackupJobId', 'N/A'),
                'resource_id': job['ResourceArn'].split('/')[-1],
                'resource_type': job.get('ResourceType', 'N/A'),
                'backup_size_gb': job.get('BackupSizeInBytes', 0) / (1024**3),
                'creation_date': job['CreationDate'].strftime('%Y-%m-%d %H:%M'),
                'completion_date': job['CompletionDate'].strftime('%Y-%m-%d %H:%M') if 'CompletionDate' in job else 'N/A',
                'state': job.get('State', 'N/A'),
                'status_message': job.get('StatusMessage', 'N/A'),
                'vault_name': job.get('BackupVaultName', 'N/A'),
                'recovery_point_arn': job.get('RecoveryPointArn', 'N/A')
            } for job in jobs]
        }
        report['storage'] = {
            'ebs_volumes': self.get_ebs_volumes(),
            'snapshots': self.get_snapshots()
        }
        return report

    def create_excel_report(self, report: Dict, output_file: str):
        """Cria relatório Excel com múltiplas planilhas de análise."""
        
        with pd.ExcelWriter(output_file, engine='xlsxwriter') as writer:
            workbook = writer.book
            
            # Formato para números
            num_format = workbook.add_format({'num_format': '#,##0.00'})
            
            # 1. Summary Report
            summary_data = {
                'Report Information': [
                    'Report Generation Date',
                    'Region',
                    'Period (days)',
                    'First Backup Date',
                    'Last Backup Date',
                    'Total Unique Resources',
                    'Total Backups',
                    'Total Size (TB)',
                    '',  # linha em branco para separar
                    'Job Status Summary:',
                    'COMPLETED',
                    'COMPLETED_WITH_ISSUES',
                    'FAILED',
                    'EXPIRED',
                    'PARTIAL'
                ],
                'Values': [
                    report['generated_at'],
                    report['region'],
                    report['period_days'],
                    min(job['creation_date'] for job in report['backups']),
                    max(job['creation_date'] for job in report['backups']),
                    len(report['unique_resources']),
                    len(report['backups']),
                    round(sum(job['backup_size_gb'] for job in report['backups']) / 1024, 2),
                    '',  # linha em branco para separar
                    '',  # cabeçalho do status summary
                    report['job_status_summary'].get('COMPLETED', 0),
                    report['job_status_summary'].get('COMPLETED_WITH_ISSUES', 0),
                    report['job_status_summary'].get('FAILED', 0),
                    report['job_status_summary'].get('EXPIRED', 0),
                    report['job_status_summary'].get('PARTIAL', 0)
                ]
            }

            df_summary = pd.DataFrame(summary_data)
            worksheet = writer.book.add_worksheet('Summary')
            df_summary.to_excel(writer, sheet_name='Summary', index=False)

            # 2. Unique Resources
            df_resources = pd.DataFrame(report['unique_resources'])
            df_resources.to_excel(writer, sheet_name='Unique Resources', index=False)
            
            # 3. Planos de Backup
            plans_data = []
            for plan in report['plans']:
                for rule in plan['rules']:
                    plans_data.append({
                        'Plan Name': plan['plan_name'],
                        'Plan ID': plan['plan_id'],
                        'Creation Date': plan['creation_date'],
                        'Rule Name': rule.get('rule_name', 'N/A'),
                        'Schedule': rule.get('schedule_expression', 'N/A'),
                        'Vault': rule.get('target_vault_name', 'N/A'),
                        'Retention Days': rule.get('lifecycle', {}).get('DeleteAfterDays', 'N/A'),
                        'Resources Count': sum(len(sel.get('resources', [])) for sel in plan['selections'])
                    })
            
            df_plans = pd.DataFrame(plans_data)
            df_plans.to_excel(writer, sheet_name='Backup Plans', index=False)

            # 4. Jobs de Backup
            df_jobs = pd.DataFrame(report['backups'])
            df_jobs.to_excel(writer, sheet_name='Backup Jobs', index=False)

            # 5. Resource Summary
            resource_summary = defaultdict(lambda: {'count': 0, 'size': 0})
            for job in report['backups']:
                res_id = job['resource_id']
                resource_summary[res_id]['count'] += 1
                resource_summary[res_id]['size'] += job['backup_size_gb']
            
            resource_data = [{
                'Resource ID': res_id,
                'Total Backups': data['count'],
                'Total Size (TB)': round(data['size'] / 1024, 2),
                'Average Size (GB)': round(data['size'] / data['count'], 2)
            } for res_id, data in resource_summary.items()]
            
            df_resource = pd.DataFrame(resource_data)
            df_resource.to_excel(writer, sheet_name='Resource Summary', index=False)

            # 6. Monthly Resource Summary
            df_jobs['Month'] = pd.to_datetime(df_jobs['creation_date']).dt.to_period('M')
            
            # 7. EBS Volumes
            df_volumes = pd.DataFrame(report['storage']['ebs_volumes'])
            df_volumes.to_excel(writer, sheet_name='EBS Volumes', index=False)

            # 8. Snapshots
            df_snapshots = pd.DataFrame(report['storage']['snapshots'])
            df_snapshots.to_excel(writer, sheet_name='Snapshots', index=False)

            # Pivot table para tamanho médio
            size_pivot = pd.pivot_table(
                df_jobs,
                values='backup_size_gb',
                index=['resource_id'],
                columns=['Month'],
                aggfunc='mean',
                fill_value=0
            )
            
            # Pivot table para contagem
            count_pivot = pd.pivot_table(
                df_jobs,
                values='backup_size_gb',
                index=['resource_id'],
                columns=['Month'],
                aggfunc='count',
                fill_value=0
            )

            # Pivot table para total
            total_pivot = pd.pivot_table(
                df_jobs,
                values='backup_size_gb',
                index=['resource_id'],
                columns=['Month'],
                aggfunc='sum',
                fill_value=0
            )

            # Combinando as três tabelas
            size_pivot.columns = [f"{col} (GB Avg)" for col in size_pivot.columns]
            count_pivot.columns = [f"{col} (Count)" for col in count_pivot.columns]
            total_pivot.columns = [f"{col} (GB Total)" for col in total_pivot.columns]

            # Reorganizando as colunas para agrupar por mês
            all_months = sorted(set([col.split(' ')[0] for col in size_pivot.columns]))
            sorted_columns = []
            for month in all_months:
                sorted_columns.extend([
                    f"{month} (Count)",
                    f"{month} (GB Avg)",
                    f"{month} (GB Total)"
                ])

            pivot_table = pd.concat([count_pivot, size_pivot, total_pivot], axis=1)
            pivot_table = pivot_table.reindex(columns=sorted_columns)
            
            pivot_table.to_excel(writer, sheet_name='Monthly Resource Summary')

    
def main():
    print("=== AWS Backup Analyzer ===")
    
    # Solicita a região ao usuário
    region = prompt_region_selection()
    print(f"\nIniciando análise na região: {region}")
    
    try:
        # Instancia o analisador com a região selecionada
        analyzer = AWSBackupAnalyzer(region)
        
        # Gera o relatório
        report = analyzer.generate_backup_report()
        
        # Salva o relatório JSON
        json_file = f'aws_backup_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        # Gera o relatório Excel
        excel_file = f'aws_backup_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        analyzer.create_excel_report(report, excel_file)
        
        print(f"\nRelatório JSON gerado: {json_file}")
        print(f"Análise Excel gerada: {excel_file}")
        print(f"Total de backups: {report['total_backups']}")
        print("\nStatus Summary:")
        for status, count in report['job_status_summary'].items():
            print(f"{status}: {count}")
            
    except Exception as e:
        print(f"\nErro durante a execução: {str(e)}")
        print("Por favor, verifique suas credenciais AWS e tente novamente.")

if __name__ == '__main__':
    main()