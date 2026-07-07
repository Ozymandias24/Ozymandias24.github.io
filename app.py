from flask import Flask, request, jsonify, render_template, Response
from flask_cors import CORS
from datetime import datetime
import json
import os

app = Flask(__name__)
CORS(app)

all_measurements = []
current_session = {
    "is_measuring": False,
    "samples": []
}
active_channels_count = 1
light_state = False


def append_sample(channels_data, current_time):
    if current_session["is_measuring"]:
        current_session["samples"].append({
            "index": len(current_session["samples"]) + 1,
            "channels": channels_data,
            "light_on": light_state,
            "timestamp": current_time.strftime('%Y-%m-%d %H:%M:%S')
        })

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if request.is_json:
            data = request.get_json()
            channels = data.get('channels', {})
            if not channels and 'value' in data:
                channels = {"ch0": data.get('value')}
                
            timestamp = data.get('timestamp')
            
            if timestamp:
                try:
                    current_time = datetime.fromtimestamp(timestamp)
                except Exception:
                    current_time = datetime.now()
            else:
                current_time = datetime.now()
                
            if channels:
                append_sample(channels, current_time)
                print(f"Received data: {channels} at {current_time}")
                return {"status": "success", "received_channels": channels, "active_channels": active_channels_count}, 200
            else:
                return {"status": "error", "message": "No valid data"}, 400
        else:
            return {"status": "error", "message": "Request must be JSON"}, 400
    else:
        return render_template('index.html')

@app.route('/data', methods=['POST'])
def receive_data():
    if request.is_json:
        data = request.get_json()
        channels = data.get('channels', {})
        if not channels and 'value' in data:
            channels = {"ch0": data.get('value')}
            
        timestamp = data.get('timestamp')
        
        if not channels:
            return {"status": "error", "message": "No valid data"}, 400
            
        if timestamp:
            try:
                current_time = datetime.fromtimestamp(timestamp)
            except Exception:
                current_time = datetime.now()
        else:
            current_time = datetime.now()
            
        append_sample(channels, current_time)
        print(f"Received data: {channels} at {current_time}")
        return {"status": "success", "received_channels": channels, "active_channels": active_channels_count}, 200
    else:
        return {"status": "error", "message": "Request must be JSON"}, 400

@app.route('/api/set_channels', methods=['POST'])
def set_channels():
    global active_channels_count
    if request.is_json:
        data = request.get_json()
        count = data.get('channels')
        if count in [1, 2, 3, 4]:
            active_channels_count = count
            return jsonify({"status": "success", "active_channels": active_channels_count}), 200
    return jsonify({"status": "error", "message": "Invalid channel count"}), 400

@app.route('/api/toggle_light', methods=['POST'])
def toggle_light():
    global light_state
    if request.is_json:
        data = request.get_json()
        if 'light_on' in data:
            light_state = bool(data['light_on'])
        else:
            light_state = not light_state
    else:
        light_state = not light_state
    return jsonify({"status": "success", "light_on": light_state}), 200

@app.route('/api/start', methods=['POST'])
def start_measurement():
    current_session["is_measuring"] = True
    current_session["samples"] = []
    
    return jsonify({"status": "success", "message": "Measurement started"}), 200

@app.route('/api/complete', methods=['POST'])
def complete_measurement():
    if not current_session["is_measuring"]:
        return jsonify({"status": "error", "message": "Not currently measuring"}), 400
        
    if len(current_session["samples"]) == 0:
        return jsonify({
            "status": "error", 
            "message": "No samples collected yet"
        }), 400
        
    all_measurements.append({
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "samples": current_session["samples"][:]
    })
    
    current_session["is_measuring"] = False
    current_session["samples"] = []
    
    return jsonify({"status": "success", "message": "Measurement completed and saved"}), 200

@app.route('/api/clear', methods=['POST'])
def clear_data():
    all_measurements.clear()
    current_session["is_measuring"] = False
    current_session["samples"] = []
    return jsonify({"status": "success", "message": "All data cleared"}), 200

@app.route('/api/latest', methods=['GET'])
def get_latest():
    latest_channels = None
    latest_ts = None
    if current_session["samples"]:
        latest = current_session["samples"][-1]
        latest_channels = latest.get("channels", {})
        if not latest_channels and "value" in latest:
             latest_channels = {"ch0": latest["value"]}
        latest_ts = latest["timestamp"]
        
    return jsonify({
        "is_measuring": current_session["is_measuring"],
        "sample_count": len(current_session["samples"]),
        "channels": latest_channels,
        "timestamp": latest_ts,
        "completed_sessions": len(all_measurements),
        "active_channels": active_channels_count,
        "light_on": light_state
    })

@app.route('/api/download', methods=['GET'])
def download_data():
    def generate():
        yield '\ufeff'
        yield 'sample_index,timestamp,light_on,ch0,ch1,ch2,ch3\n'
        for session in all_measurements:
            for s in session["samples"]:
                channels = s.get("channels", {})
                if not channels and "value" in s:
                    channels = {"ch0": s["value"]}
                ch0 = channels.get("ch0", "")
                ch1 = channels.get("ch1", "")
                ch2 = channels.get("ch2", "")
                ch3 = channels.get("ch3", "")
                light = 1 if s.get("light_on", False) else 0
                yield f"{s['index']},{s['timestamp']},{light},{ch0},{ch1},{ch2},{ch3}\n"
    
    current_time_str = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"voltage_measurements_{current_time_str}.csv"
    
    return Response(generate(), mimetype='text/csv', 
                    headers={'Content-Disposition': f'attachment; filename={filename}'})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=5000, debug=True)
