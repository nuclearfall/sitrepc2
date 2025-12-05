from sitrepc2.config.paths import gazetteer_paths


def get_lookup_files():
	locale, region, *rest = gazetteer_paths()
	return locale, region