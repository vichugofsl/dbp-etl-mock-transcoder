from flask import Flask, request, jsonify
import subprocess
import time
import os

app = Flask(__name__)
# In-memory storage for job status
jobs = {}

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
    local_path = os.environ.get('LOCAL_VIDEO_FOLDER_PATH')
    api_key = request.headers.get('X-API-Key')
    print("=======================================================================")
    print("GET Audio Transcoding Result.........")
    print("API Key: " + api_key)
    print("request.json: ")
    print(request)
    print("=======================================================================")
    job_id = int(time.time()*1000)
    input_job = request.json['input']
    input_key = input_job['key']

    outputs = request.json['output']
    # Retrieve job information from in-memory storage
    job_outputs = []
    files = []
    for output in outputs:
        dirname_output = os.path.dirname(output['key'])
        job_outputs.append({
            'bucket': output['bucket'],
            'key': dirname_output + '/' + input_key,
            'container': output['container'],
            'codec': output['codec'],
            'bitrate': output['bitrate'],
        })
        file_name_input = 'XNM___NM_Book_____FILESETID.mp3'
        file_name_output = 'XNM___NM_Book____FILESETID.mp3'
        files.append({
            'input': {
                'key': output['key'] + '/'+ file_name_input,
                'duration': 100
            },
            'output': {
                'key': dirname_output + '/' + input_key + '/' + file_name_output,
                'duration': 101
            }
        })

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
        print(job['Job'])
        return jsonify(job['Job'])
    else:
        return jsonify({'Error': 'Job not found'}), 404

if __name__ == '__main__':
    app.run(debug=True, port=5000)
