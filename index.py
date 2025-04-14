import os
import time
import logging
from flask import Flask, request, jsonify
import boto3

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# In-memory storage for job status (for demonstration purposes)
jobs = {}

# Initialize the S3 session using the desired AWS profile.
try:
    s3_session = boto3.Session(profile_name='dbp-dev')
    s3_client = s3_session.client('s3')
except Exception as e:
    logger.exception("Failed to create S3 session: %s", e)
    s3_client = None  # Allows for fallback or error messaging if needed.

# -------------------------------
# Transcoding Job Endpoints (Video)
# -------------------------------

@app.route('/2012-09-25/jobs', methods=['POST'])
def create_job():
    """
    Create a new transcoding job.
    The job simulates the FFmpeg transcoding command for each input and output combination.
    """
    try:
        job_id = str(int(time.time() * 1000))
        local_path = os.environ.get('LOCAL_VIDEO_FOLDER_PATH', '/tmp')
        pipeline_id = request.args.get('PipelineId', 'default_pipeline')
        data = request.get_json(force=True) or {}
        inputs = data.get('Inputs', [])
        output_key_prefix = data.get('OutputKeyPrefix', '')
        outputs = data.get('Outputs', [])

        resolution_map = {
            'av720p': '1280x720',
            'av480p': '854x480',
            'av360p': '640x360'
        }

        job_outputs = []

        # Fake m3u8 playlist content – you can modify this content as needed.
        fake_m3u8_content = (
            "#EXTM3U\n"
            "#EXT-X-VERSION:3\n"
            "#EXT-X-TARGETDURATION:10\n"
            "#EXT-X-MEDIA-SEQUENCE:0\n"
            "#EXTINF:10.0,\n"
            "segment_1.ts\n"
            "#EXTINF:10.0,\n"
            "segment_2.ts\n"
            "#EXT-X-ENDLIST\n"
        )

        fixed_bucket = "etl-development-input"

        for input_item in inputs:
            input_name = input_item.get('Key')
            for output in outputs:
                output_key = os.path.join(output_key_prefix, output.get('Key', ''))
                # Assume resolution keyword is the last part after splitting by underscore.
                resolution_keyword = output_key.split('_')[-1]
                resolution = resolution_map.get(resolution_keyword, '1280x720')
                segment_duration = output.get('SegmentDuration', '10')
                # Construct the FFmpeg command (mock only)
                command = [
                    'ffmpeg', '-i', os.path.join(local_path, input_name),
                    '-codec:v', 'libx264', '-codec:a', 'aac',
                    '-s', resolution, '-hls_list_size', '0', '-hls_time', segment_duration,
                    '-hls_segment_filename', f"{os.path.join(local_path, output_key)}_segment_%d.ts",
                    f"{os.path.join(local_path, output_key)}.m3u8"
                ]
                logger.info("MOCK Transcoding command: %s", command)
                job_outputs.append({
                    'Key': output_key,
                    'Status': 'Complete'
                })

            s3_key = input_name.replace('.mp4', '_stream.m3u8')
            print(f" Uploading fake m3u8 to S3: s3://{fixed_bucket}/{s3_key}")
            try:
                s3_client.put_object(
                    Bucket=fixed_bucket,
                    Key=s3_key,
                    Body=fake_m3u8_content
                )
                logger.info("Uploaded fake m3u8 to s3://%s/%s", fixed_bucket, s3_key)
            except Exception as s3_ex:
                logger.exception("Failed to upload m3u8 to S3 for key %s: %s", s3_key, s3_ex)


        response = {
            'Job': {
                'Input': inputs[0] if inputs else {},
                'Status': 'Complete',
                'Id': job_id,
                'PipelineId': pipeline_id,
                'Inputs': inputs,
                'OutputKeyPrefix': output_key_prefix,
                'Outputs': job_outputs,
            }
        }

        jobs[int(job_id)] = response
        return jsonify(response), 200

    except Exception as e:
        logger.exception("Error creating transcoding job:")
        return jsonify({'Error': 'Failed to create job', 'Message': str(e)}), 500


@app.route('/2012-09-25/jobs/<job_id>', methods=['GET'])
def get_job(job_id):
    """
    Retrieve job information by job_id.
    """
    try:
        job = jobs.get(int(job_id))
        if job:
            return jsonify(job)
        else:
            return jsonify({'Error': 'Job not found'}), 404
    except Exception as e:
        logger.exception("Error retrieving job:")
        return jsonify({'Error': 'Invalid job id', 'Message': str(e)}), 400


# -------------------------------
# Audio Transcoding Endpoints
# -------------------------------

@app.route('/job/<job_id>', methods=['GET'])
def get_audio_job(job_id):
    """
    Retrieve audio transcoding job details using the provided job_id.
    """
    api_key = request.headers.get('X-API-Key')
    logger.info("GET Audio Transcoding Result - API Key: %s", api_key)
    try:
        job = jobs.get(int(job_id))
        if job:
            return jsonify(job['Job'])
        else:
            return jsonify({'Error': 'Job not found'}), 404
    except Exception as e:
        logger.exception("Error retrieving audio job:")
        return jsonify({'Error': 'Invalid job id', 'Message': str(e)}), 400


@app.route('/job', methods=['POST'])
def run_audio_job():
    """
    Processes an audio job submission.
    Lists .mp3 files from S3 under given output paths,
    creates job output information and simulates file retrieval.
    """
    try:
        api_key = request.headers.get('X-API-Key')
        logger.info("Run Audio Job - API Key: %s", api_key)
        job_id = str(int(time.time() * 1000))
        data = request.get_json(force=True) or {}
        input_job = data.get('input', {})
        input_key = input_job.get('key')
        print(f"Input Key: {input_key}")
        outputs = data.get('output', [])
        job_outputs = []
        files = []

        for output in outputs:
            job_outputs.append({
                'bucket': output.get('bucket'),
                'key': output.get('key'),
                'container': output.get('container'),
                'codec': output.get('codec'),
                'bitrate': output.get('bitrate'),
            })

            # Retrieve the files from the specified S3 bucket and prefix
            bucket_name = output.get('bucket')
            output_key_prefix = output.get('key')
            s3_path = f"{output_key_prefix}/"
            logger.info("Listing S3 files in path: %s", s3_path)
            response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=s3_path)

            if 'Contents' in response:
                for item in response['Contents']:
                    if "Art" not in item['Key']:
                        file_name_output = os.path.basename(item['Key'])
                        files.append({
                            'input': {
                                'key': item['Key'],
                                'duration': 100  # Placeholder duration
                            },
                            'output': {
                                'key': f"{output['key']}/{file_name_output}",
                                'duration': 101  # Placeholder duration
                            }
                        })
            else:
                logger.warning("No files found in S3 path: %s", s3_path)

        job = {
            'Job': {
                'status': 'Complete',
                'id': job_id,
                'output': job_outputs,
                'files': files,
            }
        }
        jobs[job_id] = job
        return jsonify(job['Job']), 200

    except Exception as e:
        logger.exception("Error running audio job:")
        return jsonify({'Error': 'Failed to run audio job', 'Message': str(e)}), 500


# -------------------------------
# AWS Lambda Handler
# -------------------------------
# Wrap the Flask application with Mangum for AWS Lambda deployment.
try:
    from mangum import Mangum
    lambda_handler = Mangum(app)
except ImportError:
    logger.warning("Mangum is not installed; lambda_handler will not be available.")
    lambda_handler = None


# -------------------------------
# For local development
# -------------------------------
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
