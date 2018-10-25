import sublime, sublime_plugin

def wait_for_settings_and_do(settings, key, func):
    def wait_for_settings_and_do_recursive(settings, key, func, wait_time):
        loaded_settings = sublime.load_settings(settings).get(key)
        if loaded_settings is None:
            print("Fail to load ", settings)
            sublime.set_timeout(lambda: wait_for_settings_and_do_recursive(settings, key, func, wait_time * 2), wait_time)
        else:
            print("Success to load ", settings)
            func(loaded_settings)
    wait_for_settings_and_do_recursive(settings, key, func, 200)

def comment_and_empty_line_remove(content):
    arr = content.split("\n")
    results = []
    for s in arr:
        strips = s.strip()
        if strips.startswith("//") or strips == "":
            pass
        else:
            results.append(s)
    return "\n".join(results)