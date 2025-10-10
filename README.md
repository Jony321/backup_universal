## Ansible Role for Backup (Postgres, MySQL, MongoDB)

This role automates the backup process for multiple databases (Postgres, MySQL, MongoDB) to S3-compatible storage. It supports cron job configuration, notification via Apprise, and backup rotation.

### Requirements

- Python 3
- AWS CLI
- Apprise (optional for notifications)

### Role Variables

```yaml
backups:
  - database_type: ""  # postgres, mysql, mongo
    name_backup: ""  # Name of the backup
    database_name: ""  # Database name
    database_user: ""  # Database user
    database_password: ""  # Database password
    database_host: "localhost"  # Database host
    database_port: 5432  # Database port
    tmp_dir: "/tmp"  # Temporary directory for backups
    bucket_name: ""  # Bucket name
    bucket_prefix: "/backups" 
    aws_endpoint: ""  # S3 endpoint URL
    retain_count: 5  # Number of backups to retain
    exp_date: null  # Expiration in seconds
    apprise_config: "/etc/backup/apprise_config"  # Apprise config path
    cron:
      minute: "0"
      hour: "2"
      day: "*"
      month: "*"
      weekday: "*"
    notifications:
      enabled: true  # Enable notifications
      apprise_target: ""  # Apprise target URL
```

### Usage

1. Define the variables in `defaults/main.yml` or override them in your playbook.
2. Run the role to configure backups:
   ```bash
   ansible-playbook -i inventory playbook.yml
   ```
3. Verify that the backup script is copied to `/usr/local/bin/backup_universal/backup.py` on the target host.
4. Check the cron job configuration for each backup in `/etc/cron.d/`.

### Example Playbook

```yaml
- hosts: all
  roles:
    - role: backup_universal
      vars:
        backups:
          - database_type: "postgres"
            name_backup: "example_backup"
            database_name: "example_db"
            database_user: "user"
            database_password: "password"
            database_host: "localhost"
            database_port: 5432
            tmp_dir: "/tmp"
            bucket_name: "my-bucket"
            aws_endpoint: "https://s3.example.com"
            retain_count: 7
            notifications_enabled: true
            cron:
              minute: "0"
              hour: "3"
```

### Testing the Role

To test the role, you can use the following steps:

1. **Run the role in a test environment:**
   Create a playbook and inventory file for testing. For example:

   ```yaml
   - hosts: localhost
     roles:
       - role: backup_universal
         vars:
           backups:
             - database_type: "postgres"
               name_backup: "test_backup"
               database_name: "test_db"
               database_user: "test_user"
               database_password: "test_password"
               database_host: "localhost"
               database_port: 5432
               tmp_dir: "/tmp"
               bucket_name: "test-bucket"
               aws_endpoint: "https://s3.example.com"
               retain_count: 3
               notifications:
                 enabled: false
               cron:
                 minute: "0"
                 hour: "1"
   ```

   Run the playbook:
   ```bash
   ansible-playbook -i inventory test_playbook.yml
   ```

2. **Verify the backup script:**
   Ensure the script is copied to `/usr/local/bin/backup_universal/backup.py` and is executable:
   ```bash
   ls -l /usr/local/bin/backup_universal/backup.py
   ```

3. **Check cron jobs:**
   Verify that the cron job is created:
   ```bash
   crontab -l | grep backup_universal
   ```

4. **Test notifications (if enabled):**
   Manually trigger a notification using Apprise:
   ```bash
   /usr/local/bin/apprise -t "Test Notification" -b "This is a test" --config /etc/backup/apprise_config_test_backup
   ```

5. **Validate backups:**
   Check the S3 bucket to ensure backups are uploaded correctly.

6. **Clean up:**
   Remove test backups and configurations after testing.
