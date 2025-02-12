#!/usr/bin/env python3

import aws_cdk as cdk

from sms_backup_restore_cdk.sms_backup_restore_stack import SMSBackupRestoreStack

app = cdk.App()
SMSBackupRestoreStack(
    app,
    "sms-backup-restore",
    env=cdk.Environment(account="093896728566", region="us-east-1"),
)

app.synth()
