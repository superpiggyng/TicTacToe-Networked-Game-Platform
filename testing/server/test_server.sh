#!/bin/bash

run_test() {
    SERVER="localhost"
    PORT=6507

    cd ../..
    local config_file="$5"

    echo "[]" > "testing/server/test_users.json"
    python3 server.py $config_file &

    SERVER_PID=$!

    sleep 1

    local test_name="$1"
    local input_file="$2"
    local output_file="$3"
    local expected_output="$4"

    > "$output_file"

    {
        while IFS= read -r command; do
            echo "$command"
            sleep 0.5
        done < "$input_file"
    } | ncat $SERVER $PORT >> "$output_file"

    if diff -q "$output_file" "$expected_output"; then
        echo "Testcase passed: Expected out equals actual out"
    else
        echo "Test failed: Expected out not equals actual out"
        echo "Difference in output: "
        diff $output_file $expected_output
    fi

    echo "Stopping the server with SIGINT..."
    kill -9 $SERVER_PID

}

run_test "test_server" "testing/server/test_server.in" "testing/server/test_server.out" "testing/server/test_server_expected.txt" "testing/server/test_config.json"


