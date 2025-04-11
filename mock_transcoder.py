from flask import Flask, request, jsonify
import time
import os
import boto3
import logging

app = Flask(__name__)
# In-memory storage for job status
jobs = {}

# Initialize S3 session
s3_session = boto3.Session(profile_name='dbp-etl-dev')
s3_client = s3_session.client('s3')

@app.route('/2012-09-25/jobs', methods=['POST'])
def create_job():
    job_id = int(time.time()*1000)
    local_path = os.environ.get('LOCAL_VIDEO_FOLDER_PATH')
    pipeline_id = request.args.get('PipelineId')
    inputs = request.json['Inputs']
    output_key_prefix = request.json.get('OutputKeyPrefix', '')
    outputs = request.json['Outputs']
    # playlists = request.json.get('Playlists', [])

    resolution_map = {
        'av720p': '1280x720',
        'av480p': '854x480',
        'av360p': '640x360'
    }

    # Run FFmpeg for each input and output combination
    job_outputs = []
    for input in inputs:
        input_name = input['Key']
        for output in outputs:
            output_key = output_key_prefix + output['Key']
            resolution_keyword = output_key.split('_')[-1]
            resolution = resolution_map.get(resolution_keyword, '1280x720')
            segment_duration = output.get('SegmentDuration', '10')
            # Customize FFmpeg command as needed
            command = ['ffmpeg', '-i', local_path+'/'+input_name, '-codec:v', 'libx264', '-codec:a', 'aac', '-s', resolution, '-hls_list_size', '0', '-hls_time', segment_duration, '-hls_segment_filename', '{}_segment_%d.ts'.format(local_path+'/'+output_key), '{}.m3u8'.format(local_path+'/'+output_key)]
    #         subprocess.run(command, check=True)
            print("=======================================================================")
            print("MOCK Transcoding.........")
            print(command)
            print("=======================================================================")
            job_outputs.append({
                'Key': output_key,
                'Status': 'Complete'
            })

    # Process the Playlists
    # TODO: create the playlist file to wrap all resolutions

    # Return a response similar to Elastic Transcoder
    response = {
        'Job': {
            'Input': inputs[0],
            'Status': 'Complete',
            'Id': str(job_id),
            'PipelineId': pipeline_id,
            'Inputs': inputs,
            'OutputKeyPrefix': output_key_prefix,
            'Outputs': job_outputs,
            # 'Playlists': job_playlists
        }
    }

    jobs[job_id] = response

    return jsonify(response)

@app.route('/2012-09-25/jobs/<job_id>', methods=['GET'])
def get_job(job_id):
    # Retrieve job information from in-memory storage
    job = jobs.get(int(job_id))
    if job:
        return jsonify(job)
    else:
        return jsonify({'Error': 'Job not found'}), 404

@app.route('/job/<job_id>', methods=['GET'])
def get_audio_job(job_id):
    api_key = request.headers.get('X-API-Key')

    print("=======================================================================")
    print("GET Audio Transcoding Result.........")
    print("API Key: " + api_key)
    print("=======================================================================")
    # Retrieve job information from in-memory storage
    job = jobs.get(int(job_id))
    if job:
        return jsonify(job['Job'])
    else:
        return jsonify({'Error': 'Job not found'}), 404

@app.route('/job', methods=['POST'])
def run_audio_job():
    api_key = request.headers.get('X-API-Key')
    print("=======================================================================")
    print("GET Audio Transcoding Result.........")
    print("API Key: " + api_key)
    print("request.json: ")
    print(request)
    print("=======================================================================")
    job_id = int(time.time()*1000)
    input_job = request.json['input']
    print("input_job")
    print(input_job)

    outputs = request.json['output']
    print("outputs")
    print(outputs)
    # Retrieve job information from in-memory storage
    job_outputs = []
    files = []
    for output in outputs:
        job_outputs.append({
            'bucket': output['bucket'],
            'key':  output['key'],
            'container': output['container'],
            'codec': output['codec'],
            'bitrate': output['bitrate'],
        })

        # List files in the S3 bucket under the specified path
        bucket_name = output['bucket']
        output_key_prefix = output['key']
        s3_path = f"{output_key_prefix}/"
        print("s3_path")
        print(s3_path)
        response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=s3_path)

        # Populate the files array with each file's input and output details
        if 'Contents' in response:
            for item in response['Contents']:
                if "Art" not in item['Key']:
                    file_name_output = os.path.basename(item['Key'])

                    # Add file entry to files array
                    files.append({
                        'input': {
                            'key': item['Key'],
                            'duration': 100  # Placeholder for duration, could be updated with actual values if available
                        },
                        'output': {
                            'key': f"{output['key']}/{file_name_output}",
                            'duration': 101  # Placeholder for duration
                        }
                    })
        else:
            logging.warning(f"No files found in S3 path {s3_path}")

    job = {
        'Job': {
            'status': 'Complete',
            'id': str(job_id),
            'output': job_outputs,
            'files': files,
        }
    }

    jobs[job_id] = job

    if job:
        return jsonify(job['Job'])
    else:
        return jsonify({'Error': 'Job not found'}), 404

if __name__ == '__main__':
    app.run(debug=True, port=5000)
