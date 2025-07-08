import ast
import pandas as pd 
from collections import Counter
from utilFuncs import formatTuplesInList
from itertools import product
from datetime import date
import re


def giveUserInfo (dataFrame, dateFilter, fandomFilter, shipFilter, explicitFilter):
    print (f"\nFilters: \ndate: {dateFilter}, fandom: {fandomFilter is not None}, ship: {shipFilter is not None}, explicit: {explicitFilter}\n")

    tag_counts = Counter(tag.strip() for tags in dataFrame["tags"] for tag in tags)
    ship_counts = Counter(ship.strip() for ships in dataFrame["ships"] for ship in ships)

    print ("Top 10 most common tags:\n",  formatTuplesInList (tag_counts.most_common(10)))

    print ("\nTop 10 most common ships:\n", formatTuplesInList (ship_counts.most_common(10)))

    print ("\nThe average number of words read is", int (dataFrame["word_count"].mean()))

    print ("And the total words read is", int (dataFrame["word_count"].sum()))


    print("\nThe fandom percentage is:")
    formattedFandoms = dataFrame["fandom"].apply(lambda x: ", ".join(x))  # joining the fandoms into a single string (removing [ , ])

    fandomCounts = pd.Series(formattedFandoms).value_counts()
    fandomPercentages = round((fandomCounts / len(dataFrame)) * 100)
    formattedPercentages = fandomPercentages.apply (lambda x: f"{x}%")

    for fandom, percentage in formattedPercentages.head(10).items():
        print(f" {fandom}: {percentage}")


    print ("\nThe most common ship-tag combos are:")
    tag_ship_pairs = []
    for _, row in dataFrame.iterrows():
        tags = row["tags"]
        ships = row["ships"]
        if tags and ships:
            tag_ship_pairs.extend(list(product(tags, ships)))

    pairs = pd.DataFrame(tag_ship_pairs, columns=["tag", "ship"])
    tag_ship_counts = pairs.value_counts().reset_index(name="count")

    print(tag_ship_counts.head(10))



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

  
def askForShip (df : pd.DataFrame):
    filtShip = ''
    while filtShip not in ['Y', 'N']:
        print ("Filter by ship? (Y/N) ")
        filtShip = input().strip().upper()
    if filtShip == 'N':
        return None

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

    mask = df['ships'].apply(lambda x: matches_characters(x, characters))

    filtered_df = df[mask]
    print(filtered_df) 

    return filtered_df if not filtered_df.empty else None



def matches_characters(ship_tags, target_characters):
    if not isinstance(ship_tags, list):
        return False
    
    for ship in ship_tags:
        char_names_raw = re.split(r'[/&]', ship.lower())
        char_names_cleaned = [name.strip() for name in char_names_raw if name.strip()]
        
        if len(char_names_cleaned) != len(target_characters):
            continue  

        if all(any(t in ch for ch in char_names_cleaned) for t in target_characters):
            return True
  
    return False


def askForExplicit ():
    filtExplicit = ""
    while filtExplicit not in ['Y', 'N']:
        print ("Filter related to explicit content? (Y/N)")
        filtExplicit = input().strip().upper()
    if filtExplicit == 'N':
        return "none"
    
    onlyExplicit = ""
    while onlyExplicit not in ['1', '2']:
        print ("\nConsider only explicit content (1) or discard all explicit content (2)")
        onlyExplicit = input().strip().upper()
    if onlyExplicit == '1':
        return "explicit"
    return "safe"