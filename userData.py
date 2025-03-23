from imports import BeautifulSoup, pd

def processWorks (html, dataFrame):
    content = BeautifulSoup(html, "html.parser")
    work_list = content.find_all ("li", {"role" : "article"})
    rows = []
    for current_work in work_list:
        if "deleted" in current_work.get("class", []): continue
        
        id        = int (current_work.find ("h4", {"class" : "heading"}).find ("a").get ("href")[7:])

        all_ships = current_work.find_all ("li", class_= "relationships")
        ships     = [ship.find ("a", class_ = "tag").text.strip() for ship in all_ships]

        rating    = current_work.find("a", class_="help symbol question modal modal-attached").find("span", class_="text").text.strip()

        all_tags  = current_work.find_all("li", class_="freeforms")
        tags      = [tag.find("a", class_="tag").text.strip() for tag in all_tags]

        fandoms   = [f.text.strip() for f in current_work.find("h5", class_="fandoms heading").find_all("a", class_="tag")]
        
        # rounds word count to the nearest 1000 multiple 
        words_tag = current_work.find("dd", attrs={"class": "words"})
        words = int(words_tag.text.replace(",", "")) if words_tag else 0
        words = round(words / 1000) * 1000 if (words > 1000) else 1000

        rows.append([id, ships, rating, tags, fandoms, words])

    new_rows = pd.DataFrame(rows, columns = ["fic_id", "ships", "rating", "tags", "fandom", "word_count"])
    dataFrame = pd.concat ([dataFrame, new_rows], ignore_index = True)
    return dataFrame
        