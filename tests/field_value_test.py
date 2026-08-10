
def validate_fileds_value_availability(data, man_fields):
    status_pass = []
    status_fail = []

    for key in man_fields:
        if key in list(data.keys()):
            if data.get(key):
                status_pass.append(key)
            else:
                status_fail.append(key)

    if status_fail:
        return False, status_fail
    elif status_pass:
        return True, status_pass
    else:
        return 'not_tested', []
