import requests
from bs4 import BeautifulSoup
import json
import datetime
import time
import re

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

def get_data():
    get_t_data()
    with open('data/data.json', 'r') as file:
        data = file.read()
        data = json.loads(data)
    teamDataA = []
    for i in range(len(data["ranked"])):
        print(f'{data["ranked"][i]["team"]} - {datetime.datetime.strftime(datetime.datetime.now(), "%Y-%m-%d %H:%M:%S")}')
        teamData = getTeamBData(data["ranked"][i]["team"])
        if teamData is None:
            continue
        else:
            teamDataA.append(teamData)
    with open('data/teams.json', 'w') as f:
        f.write(json.dumps({
            "last_updated": f"{datetime.datetime.strftime(datetime.datetime.now(), '%Y-%m-%d %H:%M:%S')}",
            "results": len(teamDataA),
            "teams": teamDataA
        }, indent=4))
        f.close()

def getTeamBData(team):
    # team must be in the format of 16-3045
    if not re.match(r'^\d{2}-\d{4}$', team):
        return
    retries = 0
    while True:
        if retries > 8:
            return
        url = "https://scoreboard.uscyberpatriot.org/team.php?team=" + str(team)
        r = requests.get(url)
        if r.status_code != 200:
            time.sleep(5)
            retries += 1
            continue
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
        break
    return v

def get_t_data():
    url = "https://scoreboard.uscyberpatriot.org/"

    r = requests.get(url)

    if r.status_code != 200:
        print("Error: Could not connect to scoreboard" + str(r.status_code) + " " + datetime.datetime.strftime(datetime.datetime.now(), '%Y-%m-%d %H:%M:%S'))
        return
    soup = BeautifulSoup(r.text, 'html.parser')
    table = soup.find('table', {'class': 'm-0 table table-bordered table-striped table-hover table-thin'})
    rows = table.find_all('tr')

    data = []
    for row in rows:
        cols = row.find_all('td')
        cols = [ele.text.strip() for ele in cols]
        v = [ele for ele in cols if ele]
        if len(v) > 9:
            print(v)
            if v[8] == "M":
                v[8] = "Multiple Instances"
            elif v[8] == "T":
                v[8] = "Time Exceeded"
            else:
                v[8] = "None"
            data.append({
                "rank": int(v[0]),
                "team": v[1],
                "state": v[2],
                "division": v[3],
                "tier": v[4],
                "images": int(v[5]),
                "score": int(v[9]),
                "play time": v[6],
                "score time": v[7],
                "penalty": v[8],
            })
        elif len(v) > 8:
            data.append({
                "rank": int(v[0]),
                "team": v[1],
                "state": v[2],
                "division": v[3],
                "tier": v[4],
                "images": int(v[8]),
                "score": int(v[8]),
                "play time": v[6],
                "score time": v[7],
                "penalty": "None",
            })
    # Sort data into 4 lists
    #['251', '16-3045', 'AL', 'Middle School', 'Middle School', '2', '01:25:58', '00:41:05', '0', '0.00', '0.00', '0.00']
    dataA = {
        "last_updated": f"{datetime.datetime.strftime(datetime.datetime.now(), '%Y-%m-%d %H:%M:%S')}",
        "ranked": data,
        "tier": {
            "platinum": [],
            "gold": [],
            "silver": []
        },
        "division": {
            "open": [],
            "jrotc": [],
            "middle": []
        }
    }
    for i in range(1, len(data)):
        if data[i]["division"] == 'Middle School':
            data[i].pop("tier")
            dataA["division"]["middle"].append(data[i])
        elif data[i]["tier"] == 'Platinum':
            dataA["tier"]["platinum"].append(data[i])
        elif data[i]["tier"] == 'Gold':
            dataA["tier"]["gold"].append(data[i])
        elif data[i]["tier"] == 'Silver':
            dataA["tier"]["silver"].append(data[i])

    for i in range(1, len(data)):
        if data[i]["division"] == 'Open':
            dataA["division"]["open"].append(data[i])
        elif data[i]["division"] != 'Middle School':
            dataA["division"]["jrotc"].append(data[i])

    with open('data/data.json', 'w') as f:
        f.write(json.dumps(dataA, indent=4))
        f.close()