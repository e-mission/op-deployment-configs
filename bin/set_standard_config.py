import json
import argparse
import glob

if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog="generate_random_tokens")

    parser.add_argument("top_level_field")
    parser.add_argument("default_config_file")

    args = parser.parse_args()

    files_to_edit = glob.glob("*.nrel-op.json", root_dir="configs")
    print("About to modify %s files %s" % (len(files_to_edit), files_to_edit[:5]))

    default_config = json.load(open(args.default_config_file))

    for fn in files_to_edit:
        with open("configs/"+fn, "r+") as fp:
            curr_json = json.load(fp)
            curr_json[args.top_level_field] = default_config
            fp.seek(0)
            json.dump(curr_json, fp, indent=4)
            fp.truncate()
