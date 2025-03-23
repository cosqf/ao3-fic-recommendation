def formatTuplesInList (arr):
    formatted_list = [(f"{tag.strip()}: {count}") for tag, count in arr]
    return "\n ".join(formatted_list)
