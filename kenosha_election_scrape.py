import requests
import pandas as pd
import time
from bs4 import BeautifulSoup
from datetime import datetime

ELECTION_ID = 64
MUNICIPALITY_DICT = {}
DATAFRAME_LIST = []


def get_municipalities():
    """
    Gets the list of different municipalities available for the county in the dropdown menu
    """
    response = requests.get(
        f"https://apps.kenoshacounty.org/ElectionResults_v2/Municipality.aspx?eid={ELECTION_ID}&muniName=City of Kenosha&p=0"
    )
    soup = BeautifulSoup(response.text, "html.parser")
    options = soup.select('select[name="ddMunis"] option')
    values = [option.get("value") for option in options if option.get("value")]
    return values[1:]  # Removes the -1 placeholder value


def get_ward_name(soup):
    """
    Extracts the ward name from the selected option in the ddReportingUnits select element
    """
    try:
        # Find the select element with name="ddReportingUnits"
        select = soup.find("select", {"name": "ddReportingUnits"})
        if select:
            # Find the selected option within this select
            selected_option = select.find("option", selected="selected")
            if selected_option:
                return selected_option.text.strip()
        print("Warning: Could not find selected ward name in ddReportingUnits")
        return "Unknown Ward"
    except Exception as e:
        print(f"Error getting ward name: {e}")
        return "Unknown Ward"


def clean_vote_value(value):
    """
    Extracts the numeric vote count from a string containing both votes and percentage
    """
    return value.split("(")[0].strip()


def create_municipality_dictionary(muni):
    response = requests.get(
        f"https://apps.kenoshacounty.org/ElectionResults_v2/Municipality.aspx?eid={ELECTION_ID}&muniName={muni}"
    )
    soup = BeautifulSoup(response.text, "html.parser")
    options = soup.select('select[name="ddReportingUnits"] option')
    values = [option.get("value") for option in options if option.get("value")]
    values = values[1:]  # Removes the -1 placeholder value
    wards = []
    for i in values:
        wards.append(int(i))
    MUNICIPALITY_DICT[muni] = wards


def scrape_election_data(muni, ward):
    """
    Scrapes election data from the specified URL, including ward information
    """
    try:
        base_url = f"https://apps.kenoshacounty.org/ElectionResults_v2/ReportingUnits.aspx?eid={ELECTION_ID}&jid={ward}&muniName={muni}"
        response = requests.get(base_url)
        if response.status_code != 200:
            print(
                f"Failed to retrieve data for ward. Status code: {response.status_code}"
            )
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        ward_name = get_ward_name(soup)

        contest_boxes = soup.find_all("div", class_="contestBox")

        all_data = []

        for contest_box in contest_boxes:
            contest_header = contest_box.find("h1")
            if not contest_header:
                continue

            contest_name = contest_header.text.strip()

            table = contest_box.find("table", class_="resultTable")
            if not table:
                continue

            candidate_rows = table.find_all("td", class_="candtd")

            for candidate_td in candidate_rows:
                candidate_name = candidate_td.text.strip()
                row = candidate_td.parent
                if row:
                    all_tds = row.find_all("td")
                    cand_index = all_tds.index(candidate_td)
                    if cand_index + 1 < len(all_tds):
                        value_td = all_tds[cand_index + 1]
                        clean_value = clean_vote_value(value_td.text.strip())
                        candidate_name_list = candidate_name.split(" ")
                        candidate_party = candidate_name_list[0]
                        candidate_name = " ".join(candidate_name_list[1:])

                        all_data.append(
                            {
                                "Municipality": muni,
                                "Ward_Name": ward_name,
                                "Ward_Number": ward_name.split(" ")[1].strip(),
                                "Contest": contest_name,
                                "Party": candidate_party,
                                "Candidate": candidate_name,
                                "Votes": clean_value,
                            }
                        )

        if not all_data:
            print(f"No data found for ward {ward_name}")
            return None

        df = pd.DataFrame(all_data)
        DATAFRAME_LIST.append(df)

    except Exception as e:
        print(f"Error processing ward {ward_name}: {str(e)}")
        return None


munis = get_municipalities()

for m in munis:
    create_municipality_dictionary(m)

for municipality, wards in MUNICIPALITY_DICT.items():
    for ward in wards:
        scrape_election_data(municipality, ward)

results = pd.concat(DATAFRAME_LIST, ignore_index=True)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
filename = f"kenosha_election_results_all_wards_{timestamp}.csv"
results.to_csv(filename, sep="|", index=False)
print(f"\nData saved to '{filename}'")
