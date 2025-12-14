"""Test the backdoor connection to the running app."""
import sys
import time
import argparse
sys.path.insert(0, '.')

from greenlight.omni_mind.backdoor import BackdoorClient

def test_basic(client):
    """Basic connectivity test."""
    print('Testing ping...')
    result = client.ping()
    print(f'  Ping: {result}')

    print('\nListing UI elements...')
    result = client.list_ui_elements()
    print(f'  Success: {result.get("success")}')
    print(f'  Count: {result.get("count", 0)}')
    if result.get('elements'):
        for eid in list(result['elements'].keys())[:10]:
            print(f'    - {eid}')

def test_storyboard(client):
    """Test opening project and navigating to storyboard."""
    print('\nOpening project...')
    result = client.open_project('projects/Go for Orchid')
    print(f'  Result: {result}')

    time.sleep(2)

    print('\nNavigating to storyboard...')
    result = client.navigate('storyboard')
    print(f'  Result: {result}')

    time.sleep(2)

    print('\nListing UI elements after navigation...')
    result = client.list_ui_elements()
    print(f'  Count: {result.get("count", 0)}')
    if result.get('elements'):
        for eid in list(result['elements'].keys())[:15]:
            print(f'    - {eid}')

    # Test zoom slider (tests geometry manager fix)
    print('\nTesting zoom slider (grid mode - 100%)...')
    result = client.send_command('set_zoom', {'zoom': 100})
    print(f'  Result: {result}')
    time.sleep(1)

    print('\nTesting zoom slider (row mode - 0%)...')
    result = client.send_command('set_zoom', {'zoom': 0})
    print(f'  Result: {result}')
    time.sleep(1)

    print('\nTesting zoom slider (mixed - 50%)...')
    result = client.send_command('set_zoom', {'zoom': 50})
    print(f'  Result: {result}')
    time.sleep(1)

    print('\nChecking for errors after zoom changes...')
    result = client.send_command('get_errors', {})
    print(f'  Errors: {result}')

def test_director(client):
    """Test running the director pipeline."""
    print('\nOpening project...')
    result = client.open_project('projects/Go for Orchid')
    print(f'  Result: {result}')

    time.sleep(2)

    print('\nRunning director via backdoor...')
    result = client.send_command('run_director', {})
    print(f'  Result: {result}')

    time.sleep(3)

    print('\nListing UI elements...')
    result = client.list_ui_elements()
    print(f'  Count: {result.get("count", 0)}')
    if result.get('elements'):
        for eid in list(result['elements'].keys()):
            print(f'    - {eid}')

    print('\nChecking for errors...')
    result = client.send_command('get_errors', {})
    print(f'  Errors: {result}')

def main():
    parser = argparse.ArgumentParser(description='Test backdoor connection')
    parser.add_argument('--test', default='basic',
                       choices=['basic', 'storyboard', 'director', 'all'],
                       help='Test to run')
    args = parser.parse_args()

    client = BackdoorClient()

    if not client.ping():
        print('ERROR: Backdoor server not running. Start the app first.')
        return 1

    if args.test == 'basic' or args.test == 'all':
        test_basic(client)

    if args.test == 'storyboard' or args.test == 'all':
        test_storyboard(client)

    if args.test == 'director' or args.test == 'all':
        test_director(client)

    print('\n✅ Test complete')
    return 0

if __name__ == '__main__':
    sys.exit(main())

