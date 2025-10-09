#!/usr/bin/env python3
import os
import boto3
import argparse
import traceback
import subprocess
import configparser

from botocore.config import Config
from datetime import datetime, timedelta, timezone


class Backuper:
    def __init__(
            self, 
            db_type: str, 
            name_backup: str, 
            bucket_name: str,
            db_name: str,
            db_user: str,
            db_password: str,
            db_host: str,
            db_port: str,
            bucket_dir: str,
            retain_count: int,
            exp_date: int,
            container_name: int,
            credentials_file: str,
            aws_region: str,
            aws_endpoint_url: str,
            tmp_dir: str,
            apprise_conf: str
            ) -> None:
        
        self.db_type = db_type
        self.name_backup = name_backup
        self.bucket_name = bucket_name
        self.db_name = db_name
        self.db_user = db_user
        self.db_password = db_password
        self.db_host = db_host
        self.db_port = db_port
        self.bucket_dir = bucket_dir
        self.retain_count = retain_count
        self.exp_date = exp_date
        self.container_name = container_name
        self.credentials_file = credentials_file
        self.aws_access_key_id, self.aws_secret_access_key = self.__get_aws_credentials()
        self.aws_region = aws_region
        self.aws_endpoint_url = aws_endpoint_url
        self.tmp_dir = tmp_dir
        self.apprise_conf = apprise_conf

    def __get_aws_credentials(self):
        config = configparser.ConfigParser()
        config.read(self.credentials_file)
        if 'default' not in config:
            raise KeyError("'default' section is missing in the credentials file")
        return config['default']['aws_access_key_id'], config['default']['aws_secret_access_key']

    def backup(self):
        archive_name = f"{datetime.now(timezone.utc).strftime('%Y-%m-%d_%H-%M')}_{self.name_backup}"
        tmp_path = os.path.join(self.tmp_dir, archive_name)
        сontainer_dump_path = os.path.join('/tmp', archive_name)

        try:
            if self.container_name:
                print(f"Starting {self.db_type} backup: {archive_name} in container: {self.container_name}\n")   
                if self.db_type == "mysql":
                    result = self.__backup_mysql_docker(сontainer_dump_path)
                if self.db_type == "postgres":
                    result = self.__backup_postgres_docker(сontainer_dump_path)
                if self.db_type == "mongo":
                    result = self.__backup_mongo_docker(сontainer_dump_path)

                self.__check_result_backup(result)

                # Verify dump file exists in the container
                subprocess.run([
                    "docker", "exec", self.container_name, "test", "-f", сontainer_dump_path
                ], check=True)

                print(f"Copying dump file from container to directory: {self.tmp_dir}\n")
                subprocess.run([
                    "docker", "cp", f"{self.container_name}:{сontainer_dump_path}", tmp_path
                ], check=True)
                subprocess.run([
                    "docker", "exec", self.container_name, "rm", сontainer_dump_path
                ], check=True)
            else:
                print(f"Starting {self.db_type} backup: {archive_name} from host\n")  
                with open(tmp_path, 'wb') as f: 
                    if self.db_type == "mysql":
                        result = self.__backup_mysql_host(f)
                    if self.db_type == "postgres":
                        result = self.__backup_postgres_host(f)
                    if self.db_type == "mongo":
                        result = self.__backup_mongo_host(f)

                self.__check_result_backup(result)

            subprocess.run(["gzip", tmp_path], check=True)
            file_path = f"{tmp_path}.gz"
            obj_name = f"{self.bucket_dir}/{archive_name}.gz"
            self.__upload_to_s3(file_path, obj_name)

            if self.apprise_conf:
                self.__send_notification("Backup Completed", f"Backup {self.name_backup} completed successfully.", self.apprise_conf)
            else:
                print("No Apprise configuration provided. Skipping notification.\n")
        except Exception as e:
            print(f"Backup {self.db_type} failed!\n")
            traceback.print_exc()
            self.__send_notification("Backup Failed", f"{self.db_type} backup failed: {str(e)}")

    def __backup_mysql_docker(self, сontainer_dump_path):
        result = subprocess.run(
            [
                "docker", "exec", self.container_name, "mysqldump",
                "-u", self.db_user, f"-p{self.db_password}",
                self.db_name, "-r", сontainer_dump_path
            ], 
            capture_output=True, text=True
        )

        return result

    def __backup_postgres_docker(self, сontainer_dump_path):
        result = subprocess.run(
            [
                "docker", "exec", self.container_name, "pg_dump",
                    f"postgresql://{self.db_user}:{self.db_password}@"
                    f"{self.db_host}:{self.db_port}/{self.db_name}",
                    "-f", сontainer_dump_path
            ], 
            check=True
        )

        return result

    def __backup_mongo_docker(self, сontainer_dump_path):
        result = subprocess.run(
            [
                "docker", "exec", self.container_name, "mongodump",
                "--db", self.database_name, "--archive", сontainer_dump_path
            ], 
            check=True
        )
        
        return result

    def __backup_mysql_host(self, f):
        result = subprocess.run([
            "mysqldump", "-u", self.db_user, f"-p{self.db_password}", self.db_name
        ], stdout=f, check=True)
        
        return result

    def __backup_postgres_host(self, f):
        result = subprocess.run([
            "pg_dump", f"postgresql://{self.db_user}:{self.db_password}@"
            f"{self.db_host}:{self.db_port}/{self.db_name}"
        ], check=True)
        
        return result

    def __backup_mongo_host(self, f):
        result = subprocess.run([
            "mongodump", "--db", config['database_name'], "--archive"
        ], stdout=f, check=True)

        return result

    def __check_result_backup(self, result):
        if result is None:
            raise Exception(f"{self.db_type} backup failed:\n Wrong db_type \n")
        if result.returncode != 0:
            raise Exception(f"{self.db_type} backup failed:\n{result.stderr}\n")
    
    def __upload_to_s3(self, file_path, key):
        config = Config(
                request_checksum_calculation = 'WHEN_REQUIRED',
                response_checksum_validation = 'WHEN_REQUIRED',
            )
        s3 = boto3.client(
            's3',
            config=config,
            endpoint_url=self.aws_endpoint,
            aws_access_key_id=self.aws_access_key,
            aws_secret_access_key=self.aws_secret_key
        )             
            
        print(f"Uploading to S3 bucket '{self.bucket_name}' with key '{key}'\n")
        
        try:
            print(f"Uploading {file_path} to S3...\n")
            s3.upload_file(file_path, self.bucket_name, key)
            print(f"File uploaded: {file_path}\n")
            os.remove(file_path)

        except Exception as e:
            self.__send_notification("Upload Failed", f"Failed to upload {file_path} to S3: {str(e)}")
            print(f"Upload failed: {file_path} - {str(e)}\n")

    def __send_notification(title, message, config_path=None):
        if os.path.exists("/usr/local/bin/apprise") and config_path and os.path.exists(config_path):
            subprocess.run(["/usr/local/bin/apprise", "-t", title, "-b", message, "--config", config_path])
        else:
            print(f"Notification skipped: Apprise config not provided or not found.\n")

    def rotate_backups(self):
        s3 = boto3.client('s3', endpoint_url=self.aws_endpoint, aws_access_key_id=self.aws_access_key, aws_secret_access_key=self.aws_secret_key)

        print(f"Rotating backups in bucket '{self.bucket_name}' under prefix '{self.bucket_dir}'\n")
        
        objects = s3.list_objects_v2(Bucket=self.bucket_name, Prefix=self.bucket_dir).get('Contents', [])
        if not objects:
            print("No objects found for rotation.\n")
            return

        sorted_objects = sorted(objects, key=lambda x: x['LastModified'])

        if self.retain_count:
            for obj in sorted_objects[:-self.retain_count]:
                print(f"Deleting due to retain count: {obj['Key']}\n")
                s3.delete_object(Bucket=self.bucket_name, Key=obj['Key'])

        if exp_date:
            exp_date = datetime.now(timezone.utc) - timedelta(seconds=int(exp_date))
            for obj in sorted_objects:
                if obj['LastModified'] < exp_date:
                    print(f"Deleting due to expiration date: {obj['Key']}\n")
                    s3.delete_object(Bucket=self.bucket_name, Key=obj['Key'])


def parse_arguments():
    parser = argparse.ArgumentParser(description="Backup Universal Script")
    parser.add_argument("-t", "--database_type", required=True, help="Type of the database (postgres, mysql, mongo)")
    parser.add_argument("-n", "--name_backup", required=True, help="Name of the backup")
    parser.add_argument("-b", "--bucket_name", required=True, help="Name of bucket")
    parser.add_argument("-d", "--database_name", required=True, help="Name database for backup")
    parser.add_argument("-u", "--database_user", required=True, help="Database user")
    parser.add_argument("-p", "--database_password", required=True, help="Database password")
    parser.add_argument("-H", "--database_host", required=True, help="Database host")
    parser.add_argument("-P", "--database_port", required=True, type=int, help="Database port")
    parser.add_argument("-D", "--bucket_dir", help="Bucket dirrectory for backup")
    parser.add_argument("-r", "--retain_count", type=int, help="Number of backups to retain")
    parser.add_argument("-e", "--exp_date", type=int, help="Expiration date in seconds (optional)")
    parser.add_argument("--container_name", help="Docker container name (optional)")
    parser.add_argument("--aws_endpoint", help="AWS S3 endpoint (optional)")
    parser.add_argument("--tmp_dir", default="/tmp", help="Temporary directory for backups")
    parser.add_argument("--aws_access_key", help="AWS access key (optional)")
    parser.add_argument("--aws_secret_key", help="AWS secret key (optional)")
    parser.add_argument("--credentials_file", required=True, help="Path to the AWS credentials file")
    parser.add_argument("--apprise_config", help="Path to the Apprise configuration file (optional)")
    return vars(parser.parse_args())


if __name__ == "__main__":
    config = parse_arguments()
    backuper = Backuper(
        db_type=config["database_type"],
        name_backup=config["name_backup"],
        bucket_name=config["bucket_name"],
        db_name=config["database_name"],
        db_user=config["database_user"],
        db_password=config["database_password"],
        db_host=config["database_host"],
        db_port=config["database_port"],
        bucket_dir=config["bucket_dir"],
        retain_count=config["retain_count"],
        exp_date=config["exp_date"],
        container_name=config["container_name"],
        credentials_file=config["credentials_file"],
        aws_region=config["aws_region"],
        aws_endpoint_url=config["aws_endpoint_url"],
        tmp_dir=config["tmp_dir"],
        apprise_conf=config["apprise_config"]
    )
    backuper.backup()
    backuper.rotate_backups()
