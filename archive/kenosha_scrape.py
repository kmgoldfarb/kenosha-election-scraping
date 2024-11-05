import requests
import pandas as pd
import time
from bs4 import BeautifulSoup
from datetime import datetime

def get_reporting_units_values(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    options = soup.select('select[name="ddReportingUnits"] option')
    values = [option.get('value') for option in options if option.get('value')]
    return values


def clean_vote_value(value):
    """
    Extracts the numeric vote count from a string containing both votes and percentage
    """
    return value.split('(')[0].strip()


def get_ward_name(soup):
    """
    Extracts the ward name from the selected option in the ddReportingUnits select element
    """
    try:
        # Find the select element with name="ddReportingUnits"
        select = soup.find('select', {'name': 'ddReportingUnits'})
        if select:
            # Find the selected option within this select
            selected_option = select.find('option', selected="selected")
            if selected_option:
                return selected_option.text.strip()
        print("Warning: Could not find selected ward name in ddReportingUnits")
        return "Unknown Ward"
    except Exception as e:
        print(f"Error getting ward name: {e}")
        return "Unknown Ward"
    

def scrape_election_data(url, ward_number):
    """
    Scrapes election data from the specified URL, including ward information
    """
    try:
        response = requests.get(url)
        if response.status_code != 200:
            print(f"Failed to retrieve data for ward {ward_number}. Status code: {response.status_code}")
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        ward_name = get_ward_name(soup)
        
        # If we couldn't find a ward name, this might not be a valid ward page
        if ward_name == "Unknown Ward":
            return None
            
        print(f"Processing ward: {ward_name}")
        
        contest_boxes = soup.find_all('div', class_='contestBox')
        
        all_data = []
        
        for contest_box in contest_boxes:
            contest_header = contest_box.find('h1')
            if not contest_header:
                continue
                
            contest_name = contest_header.text.strip()
            
            table = contest_box.find('table', class_='resultTable')
            if not table:
                continue
            
            candidate_rows = table.find_all('td', class_='candtd')
            
            for candidate_td in candidate_rows:
                candidate_name = candidate_td.text.strip()
                row = candidate_td.parent
                if row:
                    all_tds = row.find_all('td')
                    cand_index = all_tds.index(candidate_td)
                    if cand_index + 1 < len(all_tds):
                        value_td = all_tds[cand_index + 1]
                        clean_value = clean_vote_value(value_td.text.strip())
                        
                        all_data.append({
                            'Ward_Name': ward_name,
                            'Ward_Number': ward_name.split(' ')[1].strip(),
                            'Contest': contest_name,
                            'Candidate': candidate_name,
                            'Votes': clean_value
                        })
        
        if not all_data:
            print(f"No data found for ward {ward_name}")
            return None
            
        return pd.DataFrame(all_data)
        
    except Exception as e:
        print(f"Error processing ward {ward_number}: {str(e)}")
        return None
    
    
def scrape_all_wards(base_url):
    """
    Scrapes data from all wards and combines into one DataFrame
    """
    all_results = []
    
    response = requests.get('https://apps.kenoshacounty.org/ElectionResults_v2/ReportingUnits.aspx?eid=63&jid=88&muniName=City of Kenosha')
    jid_strings = get_reporting_units_values(response.text)
    jid_ints = []
    for i in jid_strings:
        jid_ints.append(int(i))
    jid_values = jid_ints[1:] # Removes placeholder option is -1
    
    for ward in jid_values:
        current_url = base_url.replace('jid=88', f'jid={ward}')
        ward_data = scrape_election_data(current_url, ward)
        
        if ward_data is not None and not ward_data.empty:
            all_results.append(ward_data)
            
        time.sleep(1) 

    if not all_results:
        print("No data was collected from any ward")
        return None
        
    # Combine all results
    final_df = pd.concat(all_results, ignore_index=True)
    
    # Clean and convert votes to numeric
    final_df['Votes'] = final_df['Votes'].str.replace(',', '').astype(float)
    
    return final_df

base_url = "https://apps.kenoshacounty.org/ElectionResults_v2/ReportingUnits.aspx?eid=63&jid=88&muniName=City of Kenosha"
results = scrape_all_wards(base_url)

if results is not None:
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'kenosha_election_results_all_wards_{timestamp}.csv'
    results.to_csv(filename, index=False)
    print(f"\nData saved to '{filename}'")
    
