import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import MinMaxScaler, OneHotEncoder
from scipy.sparse import hstack, csr_matrix
import re
import numpy as np
from itertools import product

BOOKMARK_BOOST = 10.0       # extra weight of a bookmarked work

TAG_PRIOR_STRENGTH = 10.0   # how many "virtual works" of the user's overall taste are mixed into a ship's tags
MAX_SEARCH_TAGS = 5
PORTABLE_MIN_WORKS = 3      # a tag never read in the ship must appear in this many works...
PORTABLE_MIN_FANDOMS = 2    # ...spread over at least this many fandoms to be used as a backfill

_FIELD_PREFIX = {'fandom': 'fandom', 'orientations': 'orientation', 'ships': 'ship', 'tags': 'tag'}
_PAREN_RE = re.compile(r"\([^)]*\)")


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).lower()).strip()


def _as_str_list(value):
    if isinstance(value, list):
        return [v for v in value if isinstance(v, str)]
    if isinstance(value, str):
        return [value]
    return []


def feature_tokens(row) -> list:
    tokens = []
    for column, prefix in _FIELD_PREFIX.items():
        for item in _as_str_list(row.get(column)):
            if column in ('ships', 'tags'):
                item = _PAREN_RE.sub("", item)
            item = _normalize(item)
            if item:
                tokens.append(f"{prefix}:{item}")
    return tokens


def build_feature_tokens(df: pd.DataFrame) -> pd.Series:
    return pd.Series([feature_tokens(r) for r in df.to_dict('records')], index=df.index, dtype=object)


def _identity_analyzer(tokens):
    return tokens


def recency_from_days(days_since_latest):
    return 1 / (1 + np.exp(0.009 * (days_since_latest - 600)))


def history_weights(df: pd.DataFrame) -> np.ndarray:
    # weight of each history work: recency + bookmark boost

    visited = pd.to_datetime(df['last_visited'], errors='coerce')
    days = (visited.max() - visited).dt.days
    recency = recency_from_days(days).fillna(0.0).to_numpy(dtype=float)
    bookmarked = df['bookmarked'].eq(True).to_numpy(dtype=float)
    return recency + bookmarked * BOOKMARK_BOOST


def select_search_tags(history_df: pd.DataFrame, ship: str, exc_tags: list[str], max_tags: int = MAX_SEARCH_TAGS,
                       prior_strength: float = TAG_PRIOR_STRENGTH) -> pd.DataFrame:
    # score(tag) = (ship_works(tag) + prior_strength * overall_share(tag)) / (ship_works_total + prior_strength)

    columns = ['tag', 'score', 'source', 'ship_works', 'total_works']
    df = history_df.reset_index(drop=True)
    if df.empty:
        return pd.DataFrame(columns=columns)

    weights = history_weights(df)
    total_weight = float(weights.sum())
    in_ship = df['ships'].apply(lambda s: ship in s if isinstance(s, list) else False).to_numpy()
    ship_work_total = int(in_ship.sum())
    all_fandoms = {f for cell in df['fandom'] for f in _as_str_list(cell)}

    stats = {}  # normalized tag -> counters
    for i, row in enumerate(df.to_dict('records')):
        fandoms = set(_as_str_list(row.get('fandom')))
        for original in {t.strip() for t in _as_str_list(row.get('tags')) if t.strip()}:
            key = _normalize(original)
            st = stats.setdefault(key, {'names': {}, 'weight': 0.0, 'works': 0, 'ship_works': 0, 'fandoms': set()})
            st['names'][original] = st['names'].get(original, 0) + 1
            st['weight'] += weights[i]
            st['works'] += 1
            st['fandoms'] |= fandoms
            if in_ship[i]:
                st['ship_works'] += 1

    rows = []
    exc_keys = {_normalize(t) for t in exc_tags}

    for key, st in stats.items():
        if key in exc_keys:
            continue
        in_this_ship = st['ship_works'] > 0
        portable = len(all_fandoms) <= 1 or (
            st['works'] >= PORTABLE_MIN_WORKS
            and len(st['fandoms']) >= PORTABLE_MIN_FANDOMS
            and _PAREN_RE.search(key) is None)
        if not (in_this_ship or portable):
            continue
        overall_share = st['weight'] / total_weight if total_weight > 0 else 0.0
        score = (st['ship_works'] + prior_strength * overall_share) / (ship_work_total + prior_strength)
        name = sorted(st['names'].items(), key=lambda kv: (-kv[1], kv[0]))[0][0]  # most common spelling
        rows.append((name, score, 'ship' if in_this_ship else 'backfill', st['ship_works'], st['works'], key))

    rows.sort(key=lambda r: (-r[1], r[2] != 'ship', r[5]))      # 1) select the best scores
    chosen = rows[:max_tags]
    chosen.sort(key=lambda r: (r[2] != 'ship', -r[1], r[5]))    # 2) ship's own tags first
    return pd.DataFrame([r[:5] for r in chosen], columns=columns)


class ProfileError(Exception):
    """The history can't produce a usable reading profile. The message is meant for the user."""


def preprocess_history_data(dataFrame: pd.DataFrame):
    df = dataFrame.copy()

    # every fandom / orientation / ship / tag is one token
    df['feature_tokens'] = build_feature_tokens(df)

    # normalized word count
    word_count_scaler = MinMaxScaler()
    df['word_count_normalized'] = word_count_scaler.fit_transform(df[['word_count']])

    df['last_visited'] = pd.to_datetime(df['last_visited'], errors='coerce')

    # drop rows where last_visited couldn't be parsed
    unparseable = df['last_visited'].isna().sum()
    if unparseable > 0:
        print(f"Warning: {unparseable} rows had unparseable last_visited and will be excluded from recency scoring")
        df = df.dropna(subset=['last_visited'])

    # recency
    most_recent_date_in_history = df['last_visited'].max()
    time_diff_days = (most_recent_date_in_history - df['last_visited']).dt.days
    
    df["recency_score"] = recency_from_days(time_diff_days)
    
    return df, word_count_scaler, most_recent_date_in_history


def vectorize_all_features(preprocessed_df: pd.DataFrame, ohe_rating_encoder: OneHotEncoder):
    df = preprocessed_df.copy()

    # TF-IDF 
    tfidf_vectorizer = TfidfVectorizer(analyzer=_identity_analyzer, min_df=1, max_df=0.9)
    try:
        tfidf_matrix = tfidf_vectorizer.fit_transform(df['feature_tokens'])
    except ValueError as e:
        raise ProfileError(
            "Your reading history doesn't have enough variety to build a profile: the fandoms, "
            "ships and tags are (almost) identical across your works. Read a wider range of fics, "
            "or load more history, and try again."
        ) from e

    # one hot encoding 
    ohe_rating_sparse = ohe_rating_encoder.fit_transform(df[['rating']])

    # converting numerical data
    numerical_features = df[['word_count_normalized', 'recency_score']].values
    numerical_sparse = csr_matrix(numerical_features) 

    # combining all features
    combined_sparse_features = hstack([tfidf_matrix, ohe_rating_sparse, numerical_sparse])

    feature_names = tfidf_vectorizer.get_feature_names_out().tolist()
    feature_names.extend(ohe_rating_encoder.get_feature_names_out(['rating']).tolist())
    feature_names.extend(['word_count_normalized', 'recency_score'])

    return combined_sparse_features, tfidf_vectorizer, feature_names


def build_user_profile(combined_sparse_features, preprocessed_df: pd.DataFrame, feature_names):
    bookmark_boost: float = BOOKMARK_BOOST

    all_history_fic_vectors = csr_matrix(combined_sparse_features)
    recency_scores = preprocessed_df['recency_score'].values.astype(np.float64)
    bookmarked_status = preprocessed_df['bookmarked'].values.astype(np.float64)
    bookmarked_status = pd.array(bookmarked_status, dtype="boolean").to_numpy(dtype=float, na_value=0.0)

    weights = (recency_scores + (bookmarked_status * bookmark_boost)).astype(float)

    total_weight_sum = np.sum(weights)
    if total_weight_sum == 0:
        print("Warning: Sum of weights is zero. User profile will be a zero vector.")
        return pd.Series(0.0, index=feature_names)

    weighted_vectors = all_history_fic_vectors.multiply(weights[:, np.newaxis])
    weighted_vectors = csr_matrix(weighted_vectors)

    summed_sparse_vector = weighted_vectors.sum(axis=0)
    user_profile_vector_sparse = csr_matrix(summed_sparse_vector) / total_weight_sum

    user_profile_vector = pd.Series(user_profile_vector_sparse.toarray().flatten(), index=feature_names)

    return user_profile_vector



def score_unread_fanfics(unread_df: pd.DataFrame, user_profile: pd.Series, model_components: dict):
    df_to_score = unread_df.copy() 

    tfidf_vectorizer = model_components['tfidf_vectorizer']
    ohe_rating_encoder = model_components['ohe_rating_encoder']
    word_count_scaler = model_components['word_count_scaler']

    # same tokens as the history (one token per fandom / orientation / ship / tag)
    df_to_score['feature_tokens'] = build_feature_tokens(df_to_score)

    # normalized word count
    df_to_score['word_count'] = df_to_score['word_count'].fillna(0).clip(lower=0, upper=word_count_scaler.data_max_[0])
    df_to_score['word_count_normalized'] = word_count_scaler.transform(df_to_score[['word_count']])
    df_to_score["recency_score"] = 1 

    # TF-IDF
    unread_tfidf_matrix = tfidf_vectorizer.transform(df_to_score['feature_tokens'])

    # One-Hot Encoding
    known_ratings = ohe_rating_encoder.categories_[0]
    df_to_score['rating'] = df_to_score['rating'].where(df_to_score['rating'].isin(known_ratings), other=known_ratings[0])
    unread_ohe_rating_sparse = ohe_rating_encoder.transform(df_to_score[['rating']])

    # word count
    numerical_features_unread = df_to_score[['word_count_normalized', 'recency_score']].values
    numerical_sparse_unread = csr_matrix(numerical_features_unread)

    # combining everything
    combined_unread_features_sparse = hstack([unread_tfidf_matrix, unread_ohe_rating_sparse, numerical_sparse_unread])

    # cosine similarity
    user_profile_reshaped = user_profile.to_numpy().reshape(1, -1) # reshaping to 2D

    # Calculate similarity between user profile and each unread fic
    # The output will be a 1D array of scores, one for each unread fic
    similarity_scores = cosine_similarity(user_profile_reshaped, combined_unread_features_sparse)[0] # type: ignore

    df_to_score['recommendation_score'] = similarity_scores

    df_to_score = df_to_score.sort_values(by='recommendation_score', ascending=False)

    return df_to_score


def generate_common_ship_tags(dataFrame, ship_tag = None, tag_filter = None):
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

    if tag_filter is not None:
        pairs = pairs[pairs['tag'] == tag_filter] 

    tag_ship_counts = pairs.value_counts().reset_index(name="count")
    return tag_ship_counts


def create_user_profile_from_history(history_df: pd.DataFrame):
    if history_df.empty:
        raise ProfileError("Your reading history is empty, so there is nothing to build a profile from.")

    ohe_rating_encoder = OneHotEncoder(handle_unknown='ignore', sparse_output=True)
    ohe_rating_encoder.fit(history_df[['rating']])

    preprocessed_df, wc_scaler, most_recent = preprocess_history_data(history_df)

    combined_features_sparse, tfidf_vec, feature_names_list = vectorize_all_features(preprocessed_df, ohe_rating_encoder)

    user_profile = build_user_profile(combined_features_sparse, preprocessed_df, feature_names_list)
    user_profile = user_profile.fillna(0)

    model_components = {
        'tfidf_vectorizer': tfidf_vec,
        'ohe_rating_encoder': ohe_rating_encoder,
        'word_count_scaler': wc_scaler,
        'recency_base': most_recent,
        'feature_names': feature_names_list
    }
    return user_profile, model_components