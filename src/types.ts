export type Quota = 'FOREIGN_EMPLOYMENT' | 'GENERAL_PUBLIC' | 'OTHER'
export type Status = 'Open' | 'Upcoming' | 'Closed'

/** One issue, as written by scraper/fetch_ipos.py into public/data/ipos.json */
export interface Ipo {
  id: string
  symbol: string
  company_name: string
  sector: string | null
  units: number | null
  price: number | null
  open_date: string // YYYY-MM-DD, Nepal calendar date
  close_date: string // YYYY-MM-DD, Nepal calendar date
  issue_manager: string | null
  status: Status // as of scrape time; the UI recomputes it live
  quota_type: Quota
  quota_source: 'offer_letter' | 'tab'
  instrument: 'IPO' | 'FPO' | 'MUTUAL_FUND' | 'RIGHT_SHARE' | 'DEBENTURE'
  eligible: boolean
  source_status: string
  status_conflict: boolean
  announcement_url: string | null
  source: string
}

export interface MissingAnnouncement {
  company_name: string
  units: number | null
  quota_type: Quota
  text: string
  url?: string
}

export interface IpoFeed {
  last_updated_utc: string | null
  as_of_date_npt?: string
  warnings?: string[]
  crosscheck?: { missing_from_primary: MissingAnnouncement[] }
  ipos: Ipo[]
}

export type TabKey = 'eligible' | 'foreign' | 'general' | 'upcoming'
