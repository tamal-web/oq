import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
import joblib

FEATURE_COLS = ['Speed', 'Throttle', 'Brake', 'nGear', 'RPM', 'DRS', 'GapSeconds', 'LapNumber']


def main():
    print("Loading training dataset...")
    df = pd.read_pickle('training_dataset.pkl')
    print(f"  Loaded {len(df)} rows.")
    print(f"  Label distribution:\n{df['Overtook'].value_counts()}")

    X = df[FEATURE_COLS]
    y = df['Overtook']

    # Ensure both classes exist; stratify only when possible
    unique_classes = y.nunique()
    stratify_arg = y if unique_classes > 1 else None

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=stratify_arg
    )
    print(f"  Train: {len(X_train)}, Test: {len(X_test)}")

    print("Training RandomForestClassifier (n_estimators=200, max_depth=8)...")
    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=8,
        class_weight='balanced',
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    print("\n=== Classification Report ===")
    print(classification_report(y_test, model.predict(X_test)))

    print("Feature importances:")
    for name, importance in zip(FEATURE_COLS, model.feature_importances_):
        print(f"  {name}: {importance:.4f}")

    joblib.dump(model, 'overtake_model_monaco.pkl')
    print("\nSaved overtake_model_monaco.pkl")


if __name__ == '__main__':
    main()
