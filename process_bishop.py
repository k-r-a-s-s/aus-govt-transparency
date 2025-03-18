#!/usr/bin/env python3
"""
Process the Bishop PDF and store the data in the database with our new category system.
"""

import logging
import json
from db_handler import DatabaseHandler, Categories, Subcategories, TemporalTypes

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    """Main function to process the Bishop PDF"""
    
    # Create a sample structured data based on the PDF content
    structured_data = {
        "mp_name": "Bronwyn Kathleen Bishop",
        "party": "Liberal",
        "electorate": "Mackellar",
        "disclosures": [
            {
                "declaration_date": "2010-10-19",
                "category": Categories.ASSET,
                "sub_category": Subcategories.ASSET_REAL_ESTATE,
                "temporal_type": TemporalTypes.ONGOING,
                "entity": "Prince Alfred Parade, Newport",
                "details": "Residence",
                "pdf_url": "bishopb_43p.pdf"
            },
            {
                "declaration_date": "2010-10-19",
                "category": Categories.ASSET,
                "sub_category": Subcategories.ASSET_REAL_ESTATE,
                "temporal_type": TemporalTypes.ONGOING,
                "entity": "Barton, ACT",
                "details": "Residence",
                "pdf_url": "bishopb_43p.pdf"
            },
            {
                "declaration_date": "2010-10-19",
                "category": Categories.ASSET,
                "sub_category": Subcategories.ASSET_REAL_ESTATE,
                "temporal_type": TemporalTypes.ONGOING,
                "entity": "Potts Point, NSW",
                "details": "Investment property",
                "pdf_url": "bishopb_43p.pdf"
            },
            {
                "declaration_date": "2010-10-19",
                "category": Categories.ASSET,
                "sub_category": Subcategories.ASSET_REAL_ESTATE,
                "temporal_type": TemporalTypes.ONGOING,
                "entity": "Curtin, ACT",
                "details": "Investment property",
                "pdf_url": "bishopb_43p.pdf"
            },
            {
                "declaration_date": "2010-10-19",
                "category": Categories.ASSET,
                "sub_category": Subcategories.ASSET_REAL_ESTATE,
                "temporal_type": TemporalTypes.ONGOING,
                "entity": "Wollar, NSW",
                "details": "Investment property",
                "pdf_url": "bishopb_43p.pdf"
            },
            {
                "declaration_date": "2010-10-19",
                "category": Categories.MEMBERSHIP,
                "sub_category": Subcategories.MEMBERSHIP_PROFESSIONAL,
                "temporal_type": TemporalTypes.RECURRING,
                "entity": "Dame Pattie Menzies Liberal Foundation",
                "details": "Foundation",
                "pdf_url": "bishopb_43p.pdf"
            },
            {
                "declaration_date": "2010-10-19",
                "category": Categories.MEMBERSHIP,
                "sub_category": Subcategories.MEMBERSHIP_PROFESSIONAL,
                "temporal_type": TemporalTypes.RECURRING,
                "entity": "Gladen Cultural Exchange Institute",
                "details": "Cultural",
                "pdf_url": "bishopb_43p.pdf"
            },
            {
                "declaration_date": "2010-10-19",
                "category": Categories.MEMBERSHIP,
                "sub_category": Subcategories.MEMBERSHIP_PROFESSIONAL,
                "temporal_type": TemporalTypes.RECURRING,
                "entity": "Opera Foundation Australia",
                "details": "Cultural",
                "pdf_url": "bishopb_43p.pdf"
            },
            {
                "declaration_date": "2010-10-19",
                "category": Categories.MEMBERSHIP,
                "sub_category": Subcategories.MEMBERSHIP_PROFESSIONAL,
                "temporal_type": TemporalTypes.RECURRING,
                "entity": "NSW Bravehearts",
                "details": "Charity",
                "pdf_url": "bishopb_43p.pdf"
            },
            {
                "declaration_date": "2010-10-19",
                "category": Categories.LIABILITY,
                "sub_category": Subcategories.LIABILITY_MORTGAGE,
                "temporal_type": TemporalTypes.ONGOING,
                "entity": "ANZ Banking Group",
                "details": "Mortgage",
                "pdf_url": "bishopb_43p.pdf"
            },
            {
                "declaration_date": "2010-10-19",
                "category": Categories.LIABILITY,
                "sub_category": Subcategories.LIABILITY_CREDIT,
                "temporal_type": TemporalTypes.ONGOING,
                "entity": "ANZ",
                "details": "Credit Cards",
                "pdf_url": "bishopb_43p.pdf"
            },
            {
                "declaration_date": "2010-10-19",
                "category": Categories.LIABILITY,
                "sub_category": Subcategories.LIABILITY_CREDIT,
                "temporal_type": TemporalTypes.ONGOING,
                "entity": "Citibank",
                "details": "Credit Cards",
                "pdf_url": "bishopb_43p.pdf"
            },
            {
                "declaration_date": "2010-10-19",
                "category": Categories.LIABILITY,
                "sub_category": Subcategories.LIABILITY_CREDIT,
                "temporal_type": TemporalTypes.ONGOING,
                "entity": "American Express",
                "details": "Credit Cards",
                "pdf_url": "bishopb_43p.pdf"
            },
            {
                "declaration_date": "2010-10-19",
                "category": Categories.LIABILITY,
                "sub_category": Subcategories.LIABILITY_OTHER,
                "temporal_type": TemporalTypes.ONGOING,
                "entity": "David Jones",
                "details": "Store Cards",
                "pdf_url": "bishopb_43p.pdf"
            },
            {
                "declaration_date": "2010-10-19",
                "category": Categories.ASSET,
                "sub_category": Subcategories.ASSET_OTHER,
                "temporal_type": TemporalTypes.ONGOING,
                "entity": "ANZ Banking Group",
                "details": "Term Deposits, Online Saver Account",
                "pdf_url": "bishopb_43p.pdf"
            },
            {
                "declaration_date": "2010-10-19",
                "category": Categories.INCOME,
                "sub_category": Subcategories.INCOME_OTHER,
                "temporal_type": TemporalTypes.RECURRING,
                "entity": "Potts Point, NSW",
                "details": "Income from investment property",
                "pdf_url": "bishopb_43p.pdf"
            },
            {
                "declaration_date": "2010-10-19",
                "category": Categories.INCOME,
                "sub_category": Subcategories.INCOME_OTHER,
                "temporal_type": TemporalTypes.RECURRING,
                "entity": "Curtin, ACT",
                "details": "Income from investment property",
                "pdf_url": "bishopb_43p.pdf"
            },
            {
                "declaration_date": "2010-10-19",
                "category": Categories.INCOME,
                "sub_category": Subcategories.INCOME_OTHER,
                "temporal_type": TemporalTypes.RECURRING,
                "entity": "Wollar, NSW",
                "details": "Income from investment property",
                "pdf_url": "bishopb_43p.pdf"
            },
            {
                "declaration_date": "2010-10-19",
                "category": Categories.INCOME,
                "sub_category": Subcategories.INCOME_DIVIDEND,
                "temporal_type": TemporalTypes.RECURRING,
                "entity": "ANZ Banking Group",
                "details": "Income from Term Deposits",
                "pdf_url": "bishopb_43p.pdf"
            },
            {
                "declaration_date": "2010-10-19",
                "category": Categories.GIFT,
                "sub_category": Subcategories.GIFT_HOSPITALITY,
                "temporal_type": TemporalTypes.ONE_TIME,
                "entity": "Opera Australia",
                "details": "Tickets to the Winter season of the Australian Opera, Sydney",
                "pdf_url": "bishopb_43p.pdf"
            },
            {
                "declaration_date": "2010-10-25",
                "category": Categories.TRAVEL,
                "sub_category": Subcategories.TRAVEL_OTHER,
                "temporal_type": TemporalTypes.ONE_TIME,
                "entity": "Mr Doug Thompson",
                "details": "Charter flight from Mudgee to Sydney",
                "pdf_url": "bishopb_43p.pdf"
            },
            {
                "declaration_date": "2010-10-25",
                "category": Categories.GIFT,
                "sub_category": Subcategories.GIFT_HOSPITALITY,
                "temporal_type": TemporalTypes.ONE_TIME,
                "entity": "Mr Ashley Pittard",
                "details": "Tickets and hospitality (Ben Hur) in Sydney",
                "pdf_url": "bishopb_43p.pdf"
            },
            {
                "declaration_date": "2011-02-15",
                "category": Categories.ASSET,
                "sub_category": Subcategories.ASSET_REAL_ESTATE,
                "temporal_type": TemporalTypes.ONE_TIME,
                "entity": "Wollar, NSW",
                "details": "Sale of farm property",
                "pdf_url": "bishopb_43p.pdf"
            },
            {
                "declaration_date": "2011-02-15",
                "category": Categories.ASSET,
                "sub_category": Subcategories.ASSET_REAL_ESTATE,
                "temporal_type": TemporalTypes.ONGOING,
                "entity": "Dubbo",
                "details": "Purchase of farm property",
                "pdf_url": "bishopb_43p.pdf"
            },
            {
                "declaration_date": "2011-04-28",
                "category": Categories.GIFT,
                "sub_category": Subcategories.GIFT_ELECTRONICS,
                "temporal_type": TemporalTypes.ONE_TIME,
                "entity": "Digital Radio Plus",
                "details": "Small portable digital radio, given by Digital Radio Plus to all Federal MPs.",
                "pdf_url": "bishopb_43p.pdf"
            },
            {
                "declaration_date": "2011-08-17",
                "category": Categories.TRAVEL,
                "sub_category": Subcategories.TRAVEL_AIR,
                "temporal_type": TemporalTypes.ONE_TIME,
                "entity": "Huawei Technologies",
                "details": "Sponsored travel to Singapore and China from 1-6 August 2011. International Business class airfares, internal travel and accommodation costs were paid for by Huawei Technologies.",
                "pdf_url": "bishopb_43p.pdf"
            },
            {
                "declaration_date": "2011-08-17",
                "category": Categories.GIFT,
                "sub_category": Subcategories.GIFT_HOSPITALITY,
                "temporal_type": TemporalTypes.ONE_TIME,
                "entity": "Opera Australia",
                "details": "Two tickets to the Winter Season of the Australian Opera",
                "pdf_url": "bishopb_43p.pdf"
            },
            {
                "declaration_date": "2011-08-17",
                "category": Categories.TRAVEL,
                "sub_category": Subcategories.TRAVEL_AIR,
                "temporal_type": TemporalTypes.ONE_TIME,
                "entity": "Qantas",
                "details": "Staff member received an upgrade from Qantas economy to business class when he travelled with me from Sydney to Melbourne on 20 July 2011",
                "pdf_url": "bishopb_43p.pdf"
            },
            {
                "declaration_date": "2011-10-24",
                "category": Categories.GIFT,
                "sub_category": Subcategories.GIFT_ENTERTAINMENT,
                "temporal_type": TemporalTypes.ONE_TIME,
                "entity": "NRL",
                "details": "2 tickets to the NRL Grand Final on Sunday 2 October 2011.",
                "pdf_url": "bishopb_43p.pdf"
            },
            {
                "declaration_date": "2012-03-22",
                "category": Categories.GIFT,
                "sub_category": Subcategories.GIFT_DECORATIVE,
                "temporal_type": TemporalTypes.ONE_TIME,
                "entity": "Australia Post",
                "details": "Framed first day cover of stamp series celebrating one hundred years of compulsory enrolment",
                "pdf_url": "bishopb_43p.pdf"
            },
            {
                "declaration_date": "2012-05-17",
                "category": Categories.GIFT,
                "sub_category": Subcategories.GIFT_ENTERTAINMENT,
                "temporal_type": TemporalTypes.ONE_TIME,
                "entity": "Yes, Prime Minister",
                "details": "Attended a performance of \"Yes, Prime Minister\" on 4 April 2012 as guests. (2 tickets). Two members of my staff were also guests, along with their partners.",
                "pdf_url": "bishopb_43p.pdf"
            },
            {
                "declaration_date": "2012-05-21",
                "category": Categories.GIFT,
                "sub_category": Subcategories.GIFT_HOSPITALITY,
                "temporal_type": TemporalTypes.ONE_TIME,
                "entity": "Opera Australia",
                "details": "Two tickets to the 2012 Summer Season of Opera Australia",
                "pdf_url": "bishopb_43p.pdf"
            },
            {
                "declaration_date": "2012-05-21",
                "category": Categories.GIFT,
                "sub_category": Subcategories.GIFT_ENTERTAINMENT,
                "temporal_type": TemporalTypes.ONE_TIME,
                "entity": "Manly Sea Eagles",
                "details": "One ticket to the Manly Sea Eagles home game on 20 May 2012, to collect for the Salvation Army and view the game.",
                "pdf_url": "bishopb_43p.pdf"
            },
            {
                "declaration_date": "2012-06-18",
                "category": Categories.GIFT,
                "sub_category": Subcategories.GIFT_ENTERTAINMENT,
                "temporal_type": TemporalTypes.ONE_TIME,
                "entity": "Huawei Technologies",
                "details": "One ticket to a private box to view the State of Origin on Wednesday 13 June 2012",
                "pdf_url": "bishopb_43p.pdf"
            },
            {
                "declaration_date": "2012-07-11",
                "category": Categories.MEMBERSHIP,
                "sub_category": Subcategories.MEMBERSHIP_OTHER,
                "temporal_type": TemporalTypes.RECURRING,
                "entity": "National Press Club of Australia",
                "details": "Complimentary membership to the National Press Club of Australia",
                "pdf_url": "bishopb_43p.pdf"
            },
            {
                "declaration_date": "2012-09-14",
                "category": Categories.GIFT,
                "sub_category": Subcategories.GIFT_ENTERTAINMENT,
                "temporal_type": TemporalTypes.ONE_TIME,
                "entity": "Huawei Technologies",
                "details": "1 ticket, Bledisloe Cup, Saturday 18th August",
                "pdf_url": "bishopb_43p.pdf"
            },
            {
                "declaration_date": "2012-11-26",
                "category": Categories.GIFT,
                "sub_category": Subcategories.GIFT_ENTERTAINMENT,
                "temporal_type": TemporalTypes.ONE_TIME,
                "entity": "Huawei Technologies",
                "details": "1 Ticket, NRL Bulldogs v Rabbitohs 22nd September",
                "pdf_url": "bishopb_43p.pdf"
            },
            {
                "declaration_date": "2012-11-26",
                "category": Categories.GIFT,
                "sub_category": Subcategories.GIFT_HOSPITALITY,
                "temporal_type": TemporalTypes.ONE_TIME,
                "entity": "Opera Australia",
                "details": "Two tickets to the 2012 Winter Season of Opera Australia",
                "pdf_url": "bishopb_43p.pdf"
            },
            {
                "declaration_date": "2013-02-12",
                "category": Categories.GIFT,
                "sub_category": Subcategories.GIFT_ENTERTAINMENT,
                "temporal_type": TemporalTypes.ONE_TIME,
                "entity": "SBS Corporation",
                "details": "One ticket to a private box, Allianz Stadium, February 10 for the A-League game",
                "pdf_url": "bishopb_43p.pdf"
            },
            {
                "declaration_date": "2013-02-12",
                "category": Categories.MEMBERSHIP,
                "sub_category": Subcategories.MEMBERSHIP_OTHER,
                "temporal_type": TemporalTypes.RECURRING,
                "entity": "Qantas Chairman's Lounge",
                "details": "Complimentary membership to the Qantas Chairman's Lounge, 2013",
                "pdf_url": "bishopb_43p.pdf"
            },
            {
                "declaration_date": "2013-06-06",
                "category": Categories.MEMBERSHIP,
                "sub_category": Subcategories.MEMBERSHIP_OTHER,
                "temporal_type": TemporalTypes.RECURRING,
                "entity": "Virgin Club",
                "details": "Complimentary membership to the Virgin Club 2013.",
                "pdf_url": "bishopb_43p.pdf"
            },
            {
                "declaration_date": "2013-06-06",
                "category": Categories.GIFT,
                "sub_category": Subcategories.GIFT_DECORATIVE,
                "temporal_type": TemporalTypes.ONE_TIME,
                "entity": "Australia Post",
                "details": "Framed Stamp Series, celebrating the Centenary of Canberra",
                "pdf_url": "bishopb_43p.pdf"
            },
            {
                "declaration_date": "2013-06-06",
                "category": Categories.TRAVEL,
                "sub_category": Subcategories.TRAVEL_AIR,
                "temporal_type": TemporalTypes.ONE_TIME,
                "entity": "Hancock Prospecting Proprietary Limited",
                "details": "Flight from Canberra to Sydney for myself and a staff member.",
                "pdf_url": "bishopb_43p.pdf"
            },
            {
                "declaration_date": "2013-06-18",
                "category": Categories.GIFT,
                "sub_category": Subcategories.GIFT_HOSPITALITY,
                "temporal_type": TemporalTypes.ONE_TIME,
                "entity": "Opera Australia",
                "details": "Two tickets to the Winter season of Opera Australia.",
                "pdf_url": "bishopb_43p.pdf"
            },
            {
                "declaration_date": "2013-07-10",
                "category": Categories.GIFT,
                "sub_category": Subcategories.GIFT_ENTERTAINMENT,
                "temporal_type": TemporalTypes.ONE_TIME,
                "entity": "Australian Rugby Union Limited",
                "details": "2 tickets to the Wallabies v Lions Rugby Union on Saturday 6th July 2013",
                "pdf_url": "bishopb_43p.pdf"
            }
        ],
        "relationships": []
    }
    
    # Initialize the database handler
    db = DatabaseHandler()
    
    # Store the structured data in the database
    disclosure_ids = db.store_structured_data(structured_data)
    
    logger.info(f"Successfully stored {len(disclosure_ids)} disclosures in database")
    
    # Save the structured data to a JSON file
    with open("bishop_data.json", "w") as f:
        json.dump(structured_data, f, indent=2)
    
    logger.info(f"Saved structured data to: bishop_data.json")
    
    # Run a query to verify that the data was stored with the new category system
    verify_categories(db)
    
def verify_categories(db):
    """Verify that the data was stored with the new category system"""
    conn = db.db_path
    
    # Get connection to database
    import sqlite3
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    
    # Query for Bronwyn Bishop's disclosures with categories
    cursor.execute("""
        SELECT category, sub_category, temporal_type, COUNT(*) as count
        FROM disclosures
        WHERE mp_name = 'Bronwyn Kathleen Bishop'
        GROUP BY category, sub_category, temporal_type
        ORDER BY count DESC
    """)
    
    results = cursor.fetchall()
    
    logger.info("\nBronwyn Bishop's disclosures by category:")
    for category, sub_category, temporal_type, count in results:
        sub_cat_info = f" - {sub_category}" if sub_category else ""
        temp_info = f" ({temporal_type})" if temporal_type else ""
        logger.info(f"{category}{sub_cat_info}{temp_info}: {count} disclosures")
    
    # Close connection
    conn.close()

if __name__ == "__main__":
    main() 