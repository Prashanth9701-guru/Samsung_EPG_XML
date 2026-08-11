Validation_Output = []

def helper_fuc(num, module, summary, expected_result, status, result, Ids:str=''):
    return {'S.No': num,
            'Module': f'{module}',
            'Scenario': summary,
            'Expected Results': expected_result,
            'Status': status,
            'Issue Summary': result,
            'Asset IDs': Ids}