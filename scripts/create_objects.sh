#!/bin/bash

CWD=$(realpath "${1:-storage}")

curl --location --request POST 'http://localhost:8080/v1/module/' --form 'module_definition=@"'$CWD'/dcs_module.yaml"' --form 'module=@"'$CWD'/dcs_module.zip"'
curl --location --request POST 'http://localhost:8080/v1/module/' --form 'module_definition=@"'$CWD'/dps_module.yaml"' --form 'module=@"'$CWD'/dps_module.zip"'
curl --location --request POST 'http://localhost:8080/v1/vmi/' --form 'vmi_definition=@"'$CWD'/vmi_def.yaml"' --form 'vmi=@"'$CWD'/PSMAWindows7With7Zip.ova"'
