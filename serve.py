from flask import Flask, jsonify, Response, send_file
import json
from bs4 import BeautifulSoup
from apscheduler.schedulers.background import BackgroundScheduler
from fetcher import get_data
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import re
from io import BytesIO
import base64
import requests

app = Flask(__name__)

@app.route('/')
def index():
    return Response(open('index.html').read(), mimetype="text/html")

@app.route('/api/divisions')
def division():
    try:
        with open('data/data.json', 'r') as file:
            data = file.read()
            data = json.loads(data)
        for i in range(len(data["division"]["open"])):
            data["division"]["open"][i].pop("division")
        for i in range(len(data["division"]["jrotc"])):
            data["division"]["jrotc"][i].pop("division")
        for i in range(len(data["division"]["middle"])):
            data["division"]["middle"][i].pop("division")
        return jsonify({
            "last_updated": data["last_updated"],
            "results": (len(data["division"]["jrotc"]) + len(data["division"]["open"]) + len(data["division"]["middle"])),
            "divisions": data["division"]
        })
    except FileNotFoundError:
        return 'data/data.json not found', 404

@app.route('/api/ranked')
def ranked():
    try:
        with open('data/data.json', 'r') as file:
            data = file.read()
            data = json.loads(data)
        return jsonify({
            "last_updated": data["last_updated"],
            "results": len(data["ranked"]),
            "ranked": data["ranked"]
        })
    except FileNotFoundError:
        return 'data/data.json not found', 404

def extract_js_data(soup):
    scripts = soup.find_all('script')
    for script in scripts:
        if 'google.visualization.arrayToDataTable' in script.text:
            data_str = re.search(r'arrayToDataTable\((.*?)\);', script.text, re.DOTALL).group(1)
            data_str = re.sub(r'\s+', ' ', data_str)
            data_str = re.sub(r',\s*]', ']', data_str)
            data_str = re.sub(r'null', 'None', data_str)
            data = eval(data_str)
            return data
    return None

@app.route('/api/team/<team>')
def getTeam(team):
    # read teams.json
    try:
        with open('data/teams.json', 'r') as file:
            teams = file.read()
            teams = json.loads(teams)
    except FileNotFoundError:
        return 'data/teams.json not found', 404
    # team must be in the format of 16-3045
    if not re.match(r'^\d{2}-\d{4}$', team):
        return jsonify({
            "error": "Invalid team format. Please use the format of xx-xxxx"
        }), 400
    # check if the team exists
    d = None
    for i in teams["teams"]:
        if i["team"] == team:
            d = i
            break
    if d is None:
        return jsonify({
            "error": "Team not found"
        }), 404
    d["last_updated"] = teams["last_updated"]
    # return the team data
    return jsonify(d)

@app.route('/api/live/team/<team>')
def getTeamData(team):
    # team must be in the format of 16-3045
    if not re.match(r'^\d{2}-\d{4}$', team):
        return jsonify({
            "error": "Invalid team format. Please use the format of xx-xxxx"
        }), 400
    try:
        url = "https://scoreboard.uscyberpatriot.org/team.php?team=" + str(team)
        r = requests.get(url)
        if r.status_code != 200:
            return 'error: could not connect to scoreboard', 500
        soup = BeautifulSoup(r.text, 'html.parser')
        tables = soup.find_all('table')
        table_data = []
        
        for table in tables:
            table_rows = table.find_all('tr')
            table_values = []
            for row in table_rows:
                row_values = [cell.text for cell in row.find_all(['td', 'th'])]
                table_values.append(row_values)
            table_data.append(table_values)
        json_data = []
        if len(table_data) == 1:
            return jsonify({
                "error": "Team has not started yet. Please try again later."
            }), 404
        for table in table_data:
            keys = table[0]
            for values in table[1:]:
                json_data.append(dict(zip(keys, values)))
        x = extract_js_data(soup)
        t = []
        for z in x[1:]:
            b = {
                "time": z[0]
            }
            for y in range(1, len(z)):
                b[str(x[0][y]).split("_cp")[0]] = z[y]
            t.append(b)
        x = t
        v = {
            "team": json_data[0]["TeamNumber"],
            "score": json_data[0]["CCSScore"],
            "division": json_data[0]["Division"],
            "tier": json_data[0]["Tier"],
            "state": json_data[0]["Location"],
            "play time": json_data[0]["Play Timehh:mm:ss"],
            "score time": json_data[0]["Score Timehh:mm:ss"],
            "image data": [],
            "time data": x
        }
        for json_data_dict in json_data[1:]:
            v["image data"].append({
                "image": json_data_dict["Image"].split("_cp")[0],
                "time": json_data_dict["Time"],
                "vulnerabilities": {
                    "found": int(json_data_dict["Found"]),
                    "remaining": int(json_data_dict["Remain"]),
                    "total": int(json_data_dict["Remain"]) + int(json_data_dict["Found"])
                },
                "score": json_data_dict["Score"],
            })
        return jsonify(v)
    except Exception as e:
        return jsonify({
            "error": "An error occurred. Please try again later."
        }), 500

@app.route('/api/tier/<tier>')
def getTierData(tier):
    # tier must be in the format of Platinum, Gold, or Silver
    if tier.lower() not in ['platinum', 'gold', 'silver']:
        return jsonify({
            "error": "Invalid tier. Please use the format of Platinum, Gold, or Silver"
        }), 400
    try:
        with open('data/data.json', 'r') as file:
            data = file.read()
            data = json.loads(data)
        return jsonify({
            "last_updated": data["last_updated"],
            "results": len(data["tier"][tier.lower()]),
            "tier": data["tier"][tier.lower()]
        })
    except FileNotFoundError:
        return 'data/data.json not found', 404

@app.route('/api/graph/linear')
def getGraphData():
    try:
        with open('data/data.json', 'r') as file:
            data = file.read()
            data = json.loads(data)
        x = []
        y = []
        # sort the data by score
        data["ranked"].sort(key=lambda x: x["score"], reverse=True)
        for i in data["ranked"]:
            if i["score"] == 0:
                continue
            x.append(i["team"])
            y.append(i["score"])
        plt.bar(x, y)
        plt.xlabel("Team")
        plt.ylabel("Score")
        plt.title("CyberPatriot Scoreboard")
        # do not show the team numbers on the x axis
        plt.xticks([])
        # set plt to 1920x1080
        plt.gcf().set_size_inches(19.2, 10.8)
        # send the plot to the client
        plt.savefig('graphs/plot.png')
        plt.close()
        return send_file('graphs/plot.png', mimetype='image/png')
    except FileNotFoundError:
        return 'data/data.json not found', 404

@app.route('/api/graph/bell')
def getBellData():
    try:
        with open('data/data.json', 'r') as file:
            data = file.read()
            data = json.loads(data)
        # make a bell curve of the scores
        x = []
        y = []
        # sort the data by score
        data["ranked"].sort(key=lambda x: x["score"], reverse=True)
        highest = data["ranked"][0]["score"]
        lowest = data["ranked"][-1]["score"]
        # calculate the mean
        mean = 0
        for i in data["ranked"]:
            mean += i["score"]
        mean /= len(data["ranked"])
        # calculate the standard deviation
        std = 0
        for i in data["ranked"]:
            std += (i["score"] - mean) ** 2
        std /= len(data["ranked"])
        std = std ** 0.5
        # calculate the bell curve
        for i in range(lowest, highest):
            x.append(i)
            y.append(1 / (std * (2 * 3.14159) ** 0.5) * 2.71828 ** (-1 / 2 * ((i - mean) / std) ** 2))
        plt.plot(x, y)
        # add standard deviation lines
        plt.xlim(lowest, highest)
        plt.axvline(mean + std, color='r', linestyle='--')
        plt.axvline(mean - std, color='r', linestyle='--')
        plt.axvline(mean + std * 2, color='r', linestyle='--')
        plt.axvline(mean - std * 2, color='r', linestyle='--')
        plt.axvline(mean + std * 3, color='r', linestyle='--')
        plt.axvline(mean - std * 3, color='r', linestyle='--')

        plt.xlabel("Score")
        plt.ylabel("Frequency")
        plt.title("CyberPatriot Scoreboard")
        # hide y labels
        plt.yticks([])
        # set plt to 1920x1080
        plt.gcf().set_size_inches(19.2, 10.8)
        # send the plot to the client
        plt.savefig('graphs/plot.png')
        plt.close()
        return send_file('graphs/plot.png', mimetype='image/png')
    except FileNotFoundError:
        return 'data/data.json not found', 404
    
# create a bell curve and add a line where the team is
@app.route('/api/graph/bell/<team>')
def getTeamBellData(team):
    # team must be in the format of 16-3045
    if not re.match(r'^\d{2}-\d{4}$', team):
        return jsonify({
            "error": "Invalid team format. Please use the format of xx-xxxx"
        }), 400
    try:
        with open('data/data.json', 'r') as file:
            data = file.read()
            data = json.loads(data)
        # make a bell curve of the scores
        x = []
        y = []
        # sort the data by score
        data["ranked"].sort(key=lambda x: x["score"], reverse=True)
        highest = data["ranked"][0]["score"]
        lowest = data["ranked"][-1]["score"]
        # calculate the mean
        mean = 0
        for i in data["ranked"]:
            mean += i["score"]
        mean /= len(data["ranked"])
        # calculate the standard deviation
        std = 0
        for i in data["ranked"]:
            std += (i["score"] - mean) ** 2
        std /= len(data["ranked"])
        std = std ** 0.5
        # calculate the bell curve
        for i in range(lowest, highest):
            x.append(i)
            y.append(1 / (std * (2 * 3.14159) ** 0.5) * 2.71828 ** (-1 / 2 * ((i - mean) / std) ** 2))
        
        for i in range(len(data["ranked"])):
            if data["ranked"][i]["team"] == team:
                if (mean + std * 3) < data["ranked"][i]["score"]:
                    plt.axvline(data["ranked"][i]["score"], color='green')
                elif (mean + std * 2) < data["ranked"][i]["score"]:
                    plt.axvline(data["ranked"][i]["score"], color='lime')
                elif (mean + std) < data["ranked"][i]["score"]:
                    plt.axvline(data["ranked"][i]["score"], color='yellow')
                elif (mean - std) < data["ranked"][i]["score"]:
                    plt.axvline(data["ranked"][i]["score"], color='orange')
                else:
                    plt.axvline(data["ranked"][i]["score"], color='r')
                break
        # add standard deviation lines
        plt.xlim(lowest, highest)
        plt.axvline(mean + std, color='violet', linestyle='--')
        plt.axvline(mean - std, color='violet', linestyle='--')
        plt.axvline(mean + std * 2, color='purple', linestyle='--')
        plt.axvline(mean - std * 2, color='purple', linestyle='--')
        plt.axvline(mean + std * 3, color='hotpink', linestyle='--')
        plt.axvline(mean - std * 3, color='hotpink', linestyle='--')
        plt.plot(x, y)
        # add the team's score

        plt.xlabel("Score")
        plt.ylabel("Frequency")
        plt.title("CyberPatriot Scoreboard")
        plt.legend([f"Team {team}", "Mean", "1 Standard Deviation", "2 Standard Deviations", "3 Standard Deviations"])
        # hide y labels
        plt.yticks([])
        # set plt to 1920x1080
        plt.gcf().set_size_inches(19.2, 10.8)
        # send the plot to the client
        plt.savefig('graphs/plot.png')
        plt.close()
        return send_file('graphs/plot.png', mimetype='image/png')
    except FileNotFoundError:
        return 'data/data.json not found', 404

if __name__ == '__main__':
    scheduler = BackgroundScheduler()
    scheduler.add_job(get_data, 'interval', seconds=(60 * 30))
    scheduler.start()
    app.run()