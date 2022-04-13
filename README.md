This is a Python script that creates an Octopus export task for all projects in a space. This is useful for creating space backups.

An example of how to run this script and upload the results to an S3 bucket is shown below:

```
cd OctopusSpaceExport
pip3 install -r requirements.txt
python3 main.py --octopusUrl https://yourinstancename.app --octopusApiKey #{Octopus.ApiKey}  --octopusSpace "#{Octopus.Space.Name}" --exportPassword #{Export.Password}

aws s3 cp . s3://contentteamspacebackup/ --recursive --exclude "*" --include "*.zip" --include "*.json"
```
