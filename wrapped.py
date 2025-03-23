from imports import ast, Counter, pd, product
from utilFuncs import formatTuplesInList


def giveUserInfo (dataFrame):
    #converting strings into actual lists
    for col in ["ships", "tags", "fandom"]:
        dataFrame[col] = dataFrame[col].apply(lambda x: ast.literal_eval(x) if isinstance(x, str) else x)

    tag_counts = Counter(tag.strip() for tags in dataFrame["tags"] for tag in tags)
    ship_counts = Counter(ship.strip() for ships in dataFrame["ships"] for ship in ships)

    print ("Top 10 most common tags:\n",  formatTuplesInList (tag_counts.most_common(10)))

    print ("\nTop 10 most common ships:\n", formatTuplesInList (ship_counts.most_common(10)))

    print ("\nThe average number of words read is", int (dataFrame["word_count"].mean()))

    print ("And the total words read is", int (dataFrame["word_count"].sum()))


    print("\nThe fandom percentage is:")
    dataFrame["fandom"] = dataFrame["fandom"].apply(lambda x: ", ".join(x))  # joining the fandoms into a single string (removing [ , ])

    fandomCounts = pd.Series(dataFrame["fandom"]).value_counts()
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

