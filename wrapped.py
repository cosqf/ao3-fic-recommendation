import pandas as pd 
from collections import Counter
from itertools import product
from datetime import date
import re

def giveWrapped (dataFrame):
    while True:
        applyFilter = ""
        while applyFilter not in ["Y", "N"]:
            applyFilter = input ("Apply filters to history summary? (Y/N): ").strip().upper()

        if applyFilter == "Y":
            dateFilter = askForDate()
            fandomFilter = askForFandom(dataFrame)
            shipFilter = askForShip (dataFrame, True)
            explicitFilter = askForExplicit ()
            orientationFilter = askForOrientation()
            giveUserInfo (dataFrame, dateFilter, fandomFilter, shipFilter, explicitFilter, orientationFilter)
        else:
            giveUserInfo (dataFrame)

        filterAgain = ""
        while filterAgain not in ["Y", "N"]:
            filterAgain = input ("Choose different filters? (Y/N): ").strip().upper()
        if filterAgain == "N":
            break


def formatTuplesInList (arr):
    formatted_list = [(f"{tag.strip()}: {count}") for tag, count in arr]
    return "\n ".join(formatted_list)

def giveUserInfo (df, dateFilter = None, fandomFilter = None, shipFilter = None, explicitFilter = None, orientationFilter = None):
    print (f"\nFilters: \ndate: {dateFilter}, fandom: {fandomFilter is not None}, ship: {shipFilter is not None}, explicit: {explicitFilter}, orientation: {orientationFilter}\n")
    print (f"size: {len(df)}")
    dataFrame = apply_filters (df, dateFilter, fandomFilter, shipFilter, explicitFilter, orientationFilter)
    if dataFrame.empty:
        print ("Empty history, loosen the filters.\n")
        return

    print (f"{len(dataFrame)} total works\n")

    tag_counts = Counter(tag.strip() for tags in dataFrame["tags"] if tags is not None for tag in tags)
    ship_counts = Counter(ship.strip() for ships in dataFrame["ships"] if ships is not None for ship in ships)

    print ("Top 10 most common tags:\n", formatTuplesInList (tag_counts.most_common(10)))

    print ("\nTop 10 most common ships:\n", formatTuplesInList (ship_counts.most_common(10)))

    print ("\nThe average number of words read is", int (dataFrame["word_count"].mean()))

    print ("And the total words read is", int (dataFrame["word_count"].sum()))


    print("\nThe fandom percentage is:")
    formattedFandoms = dataFrame["fandom"].apply(lambda x: ", ".join(x) if isinstance (x, list) else x)  # joining the fandoms into a single string (removing [ , ])

    fandomCounts = pd.Series(formattedFandoms).value_counts()
    fandomPercentages = round((fandomCounts / len(dataFrame)) * 100)
    f_formattedPercentages = fandomPercentages.apply (lambda x: f"{round(x)}%")

    for fandom, percentage in f_formattedPercentages.head(10).items():
        print(f" {fandom}: {percentage}")

    print ("\nThe orientation percentage is:")
    formattedOrientations = dataFrame["orientations"].apply(lambda x: ", ".join(x) if isinstance (x, list) else x)

    orientationCounts = pd.Series(formattedOrientations).value_counts()
    orientationPercentages = round((orientationCounts / len(dataFrame)) * 100)
    o_formattedPercentages = orientationPercentages.apply (lambda x: f"{round(x)}%")

    for orientation, percentage in o_formattedPercentages.head(10).items():
        print(f" {orientation}: {percentage}")

    print ("\nThe most common ship-tag combos are:")
    tag_ship_counts = generate_common_ship_tags(dataFrame)

    print(tag_ship_counts.head(10))

def generate_common_ship_tags(dataFrame, ship_tag = None):
    tag_ship_pairs = []
    for _, row in dataFrame.iterrows():
        tags = row["tags"]
        ships = row["ships"]
        if not isinstance(tags, list):
            tags = [tags] if pd.notna(tags) else []
        if not isinstance(ships, list):
            ships = [ships] if pd.notna(ships) else []

        if tags and ships:
            tag_ship_pairs.extend(list(product(tags, ships)))

    pairs = pd.DataFrame(tag_ship_pairs, columns=["tag", "ship"])

    if ship_tag is not None:
        pairs = pairs[pairs['ship'] == ship_tag] 

    tag_ship_counts = pairs.value_counts().reset_index(name="count")
    return tag_ship_counts


def apply_filters(df: pd.DataFrame, dateFilter = None, fandomFilter = None, shipFilter = None, explicitFilter = None, orientationFilter = None):
    if df.empty:
        return pd.DataFrame()

    f_df = df.copy() 

    if shipFilter is not None:
        f_df = f_df[shipFilter]

    if fandomFilter is not None:
        f_df = f_df[fandomFilter]

    if orientationFilter is not None:
       mask = f_df['orientations'].apply(lambda x: orientationFilter in x)
       f_df = f_df[mask]

    if dateFilter is not None:
        mask = f_df['last_visited'].apply(lambda x: x.date() >= dateFilter) 
        f_df = f_df[mask]

    if explicitFilter is not None:
        if explicitFilter == 'safe':
            mask = f_df['rating'].apply(lambda x: x != 'Explicit') 
            f_df = f_df[mask]
        elif explicitFilter == 'explicit': 
            mask = f_df['rating'].apply(lambda x: x == 'Explicit')
            f_df = f_df[mask]

    return f_df


def askForDate():
    filtDate = ''
    while filtDate not in ['Y', 'N']:
        print ("Filter by date? (Y/N) ")
        filtDate = input().strip().upper()
    if filtDate == 'N':
        return None

    print ("Only works from the date you insert onwards will be considered.")

    year = None
    while year is None: 
        year_raw = input("Insert the year (e.g., 2023): ").strip()
        if not year_raw.isdigit():
            print("Invalid input. Please enter a number for the year.")
            continue
        try:
            year = int(year_raw)
        except ValueError:
            print("Invalid number format for year. Please re-enter.")
            year = None

    month = None
    while month is None:
        month_raw = input("Insert the month (number, 1-12): ").strip()
        if not month_raw.isdigit():
            print("Invalid input. Please enter a number for the month.")
            continue
        try:
            month = int(month_raw)
            if not (1 <= month <= 12):
                print("Month must be between 1 and 12. Please re-enter.")
                month = None
        except ValueError:
            print("Invalid number format for month. Please re-enter.")
            month = None

    day = None
    while day is None:
        day_raw = input("Insert the day (1-31): ").strip()
        if not day_raw.isdigit():
            print("Invalid input. Please enter a number for the day.")
            continue
        try:
            day = int(day_raw)
            if not (1 <= day <= 31):
                print("Day must be between 1 and 31. Please re-enter.")
                day = None
        except ValueError:
            print("Invalid number format for day. Please re-enter.")
            day = None
    
    # validation
    try:
        return date(year, month, day)
    except ValueError as e:
        print(f"Error: The date {year}-{month}-{day} is not a valid calendar date. {e}")
        return askForDate()

        

def askForFandom(df : pd.DataFrame):
    filtfandom = ''
    while filtfandom not in ['Y', 'N']:
        print ("Filter by fandom? (Y/N) ")
        filtfandom = input().strip().upper()
    if filtfandom == 'N':
        return None

    print ("Only works from the fandom you insert onwards will be considered.")

    fandom = input ("Insert the name of the fandom: ").strip().lower()
    fandom_found_mask = df['fandom'].apply (lambda x: any(fandom in f.lower() for f in x))

    if fandom_found_mask.any():
        return fandom_found_mask
    else:
        print ("Fandom wasn't found. Ensure you're not abbreviating or re-check the name in AO3.")
        return askForFandom(df)

  
def askForShip (df : pd.DataFrame, ask: bool):
    if (ask):
        filtShip = ''
        while filtShip not in ['Y', 'N']:
            print ("Filter by ship? (Y/N) ")
            filtShip = input().strip().upper()
        if filtShip == 'N':
            return None, None
        print ("Only works from the ship you insert onwards will be considered.")

    characters = []
    number_characters = None
    while number_characters is None: 
        number_characters_raw = input ("Insert the number of characters in the ship: ").strip()
        if not number_characters_raw.isdigit():
            print("Invalid input. Please enter a number.")
            continue
        try:
            number_characters = int(number_characters_raw)
            if not (number_characters > 1):
                print("Must be more than one.")
                number_characters = None
        except ValueError:
            print("Invalid number format. Please re-enter.")
            number_characters = None

    for i in range(number_characters):
        name = input(f"Insert the name of character {i+1}: ").strip().lower()
        characters.append(name)
    results_df = df['ships'].apply(lambda x: pd.Series (matches_characters (x, characters)))
    mask_series = results_df[0]
    ship_tag_series = results_df[1]
   
    matched_tags = ship_tag_series.dropna().tolist()

    return mask_series, matched_tags[0]



def matches_characters(ship_tags, target_characters):
    if not isinstance(ship_tags, list):
        return False
    
    for ship in ship_tags:
        char_names_raw = re.split(r'[/&]', ship.lower())
        char_names_cleaned = [name.strip() for name in char_names_raw if name.strip()]
        
        if len(char_names_cleaned) != len(target_characters):
            continue  

        if all(any(target in character for character in char_names_cleaned) for target in target_characters):
            return True, ship
  
    return False


def askForExplicit ():
    filtExplicit = ""
    while filtExplicit not in ['Y', 'N']:
        print ("Filter related to explicit content? (Y/N)")
        filtExplicit = input().strip().upper()
    if filtExplicit == 'N':
        return None
    
    onlyExplicit = ""
    while onlyExplicit not in ['1', '2']:
        print ("\nConsider only explicit content (1) or discard all explicit content (2)")
        onlyExplicit = input().strip().upper()
    if onlyExplicit == '1':
        return "explicit"
    return "safe"


def askForOrientation ():
    filtOrientation = ""
    while filtOrientation not in ['Y', 'N']:
        print ("Filter related to the orientation of the relationships? (Y/N)")
        filtOrientation = input().strip().upper()
    if filtOrientation == 'N':
        return None
    
    options = {
        '1': "F/F: female/female relationships",
        '2': "F/M: female/male relationships",
        '3': "Gen: no romantic or sexual relationships, or relationships which are not the main focus of the work",
        '4': "M/M: male/male relationships",
        '5': "Multi: more than one kind of relationship, or a relationship with multiple partners",
        '6': "Other"
    }
    
    options_display = "\nConsider only: \n"
    for key, value in options.items():
        options_display += f"{value} ({key})\n"

    while True:
        print(options_display)
        
        user_input = input("Enter your choice (1-6): ").strip()
        if user_input in options:
            return options[user_input].split(': ')[0] 
        else:
            print(f"Invalid input: '{user_input}'. Please enter a number between 1 and 6.")
