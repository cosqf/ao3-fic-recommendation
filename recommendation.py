import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import MinMaxScaler, OneHotEncoder
from scipy.sparse import hstack, csr_matrix
import numpy as np

def preprocess_history_data(dataFrame: pd.DataFrame):
    df = dataFrame.copy()
    
    # preparation for vectorizing text data
    text_columns = ['fandom', 'orientations', 'ships', 'tags']
    for c in text_columns:
        df[f"{c}_str"] = df[c].apply(lambda x: ' '.join(map(str, x)) if isinstance(x, list) else str(x) if pd.notna(x) else '')
    
    df['combined_text_features'] = df[[f"{c}_str" for c in text_columns]].agg(' '.join, axis=1)
    df['combined_text_features'] = df['combined_text_features'].str.lower().str.replace('[^a-z0-9, ]', ' ', regex=True).str.strip().str.replace(r'\s+', ' ', regex=True)

    # normalized word count
    word_count_scaler = MinMaxScaler()
    df['word_count_normalized'] = word_count_scaler.fit_transform(df[['word_count']])

    # recency
    most_recent_date_in_history = df['last_visited'].max()
    time_diff_days = (most_recent_date_in_history - df['last_visited']).dt.days
    
    df["recency_score"] = 1 / (1 + np.exp(0.009 * (time_diff_days - 600)))
    
    return df, word_count_scaler, most_recent_date_in_history


def vectorize_all_features(preprocessed_df: pd.DataFrame, ohe_rating_encoder: OneHotEncoder):
    df = preprocessed_df.copy()

    # TF-IDF 
    tfidf_vectorizer = TfidfVectorizer(stop_words='english', min_df=2, max_df=0.9)
    tfidf_matrix = tfidf_vectorizer.fit_transform(df['combined_text_features'])

    # one hot encoding 
    ohe_rating_sparse = ohe_rating_encoder.transform(df[['rating']])

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
    bookmark_boost: float = 3.0 

    all_history_indices = preprocessed_df.index.tolist()
    all_history_fic_vectors = combined_sparse_features[all_history_indices]
    recency_scores = preprocessed_df.loc[all_history_indices, 'recency_score'].values

    bookmarked_status = preprocessed_df.loc[all_history_indices, 'bookmarked'].values

    weights = recency_scores.copy()
    weights[bookmarked_status] *= bookmark_boost  # type: ignore

    total_weight_sum = np.sum(weights) # type: ignore
    if total_weight_sum == 0:
        print("Warning: Sum of weights is zero. User profile will be a zero vector.")
        return pd.Series(0.0, index=feature_names)

    weighted_vectors = all_history_fic_vectors.multiply(weights[:, np.newaxis]) # type: ignore

    summed_sparse_vector = weighted_vectors.sum(axis=0)
    user_profile_vector_sparse = csr_matrix(summed_sparse_vector) / total_weight_sum

    user_profile_vector = pd.Series(user_profile_vector_sparse.toarray().flatten(), index=feature_names)

    return user_profile_vector


def create_user_profile_from_history(history_df: pd.DataFrame):
    ohe_rating_encoder = OneHotEncoder(handle_unknown='ignore', sparse_output=True)
    ohe_rating_encoder.fit(history_df[['rating']])

    preprocessed_df, wc_scaler, most_recent = preprocess_history_data(history_df)

    combined_features_sparse, tfidf_vec, feature_names_list = vectorize_all_features(preprocessed_df, ohe_rating_encoder)

    user_profile = build_user_profile(combined_features_sparse, preprocessed_df, feature_names_list)
    
    model_components = {
        'tfidf_vectorizer': tfidf_vec,
        'ohe_rating_encoder': ohe_rating_encoder,
        'word_count_scaler': wc_scaler,
        'recency_base': most_recent,
        'feature_names': feature_names_list
    }

    return user_profile, model_components