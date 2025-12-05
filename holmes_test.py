from holmes_extractor import Manager

def main():
    # You can keep defaults or tweak number_of_workers if you want
    manager = Manager(
        "en_core_web_lg",
        perform_coreference_resolution=True,
        number_of_workers=2,   # optional, just to keep things simple
    )

    print("Holmes initialized OK.")
    result = manager.match(
        search_phrase_text="Russia shelled a town",
        document_text="Russia shelled Avdiivka yesterday."
    )
    print("Matches:", result)

if __name__ == "__main__":
    main()
