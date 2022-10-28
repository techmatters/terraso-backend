#!/usr/bin/env bash

set -o errexit


submit_render_job() {
    local service_name=$1
    local token=$2
    local command=$3
    local endpoint="https://api.render.com/v1/services/${service_name}/jobs"

    curl --request POST $endpoint \
         --header "Authorization: Bearer $token" \
         --header "Content-Type: application/json" \
         --data-raw "{\"startCommand\": \"python3 terraso_backend.py $command\"}" \
        | jq '.id'
}


check_job_status() {
    local service_name=$1
    local job_id=$2
    local token=$3
    local endpoint="https://api.render.com/v1/services/${service_name}/jobs/{$job_id}"

    curl --request GET $endpoint --header "Authorization: Bearer $token" | jq '.status'
}


render_job() {
    local service_name=$1
    local token=$2
    local command=$3

    local job_id=$(submit_render_job $service_name $token $command)
    local status=null
    while [ $status = 'null' ]; do
        status=$(check_job_status)
        sleep 5
        if [ $status = 'failed' ]; then
            exit 1
        fi
    done

}


sync_buckets() {
    # buckets provided as a comma separated string (i.e. bucket1,bucket2)
    local from_buckets=($(echo $1 | tr ',' '\n'))
    local to_buckets=($(echo $2 | tr ',' '\n'))
    local num_from=${#from_buckets[@]}
    local num_to=${#to_buckets[@]}
    if [ $num_from != $num_to ]; then
        echo "Need same number of from_buckets (${num_from}) and to_buckets (${num_to})" 1>&2
        exit 1
    fi
    for i in ${from_buckets[@]}; do
        aws s3 sync from_buckets[$i] to_buckets[$i]
    done
}

require() {
    local var_names=$1
    for var_name in "${var_names[@]}"; do
        if [ -z ${$var_name} ]; then
            echo "Variable $var_name needs to be defined" 1>&2
            exit 1
        fi
    done
}


main() {

    require "RENDER_TOKEN"
    require "URL_REWRITES_CONFIG_FILE"
    require "SOURCE_S3_BUCKETS"
    require "TARGET_S3_BUCKETS"
    require "SOURCE_SERVICE"
    require "TARGET_SERVICE"

    sync_buckets $SOURCE_S3_BUCKETS $TARGET_S3_BUCKETS
    render_job $SOURCE_SERVICE $RENDER_TOKEN 'backup --s3'
    render_job $TARGET_SERVICE $RENDER_TOKEN "loadbackup --s3 --url-rewrites $URL_REWRITES_CONFIG_FILE"
}

main $@
