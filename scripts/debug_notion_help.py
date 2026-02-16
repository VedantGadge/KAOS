from notion_client import Client

def check_help():
    notion = Client(auth="dummy")
    print(help(notion.databases))

if __name__ == "__main__":
    check_help()
