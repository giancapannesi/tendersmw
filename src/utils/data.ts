import fs from 'node:fs';
import path from 'node:path';

export interface Tender {
  title: string;
  slug: string;
  reference_number: string;
  source: string;
  source_url: string;
  procuring_entity: string;
  procuring_entity_slug: string;
  entity_type: string;
  tender_type: string;
  procurement_method: string;
  category: string;
  subcategories: string[];
  sectors: string[];
  description_short: string;
  description_long: string;
  country: string;
  region: string;
  city: string;
  published_date: string;
  closing_date: string;
  closing_time: string;
  estimated_value: number | null;
  currency: string;
  funding_source: string;
  donor: string | null;
  document_urls: { name: string; url: string; type: string }[];
  contact_email: string;
  contact_phone: string;
  status: string;
  is_active: boolean;
  days_remaining: number;
  similar_tenders: string[];
  last_updated: string;
  review_status: string;
  quality_score: number;
  has_been_enriched: boolean;
}

export interface Category {
  name: string;
  slug: string;
  description: string;
  icon: string;
  count?: number;
}

const tendersDir = path.join(process.cwd(), 'src/content/tenders');
const categoriesDir = path.join(process.cwd(), 'src/content/categories');

let _tenderCache: Tender[] | null = null;
let _categoryCache: Category[] | null = null;

export function getAllTenders(): Tender[] {
  if (_tenderCache) return _tenderCache;

  if (!fs.existsSync(tendersDir)) return [];

  const files = fs.readdirSync(tendersDir).filter(f => f.endsWith('.json'));
  const tenders = files.map(f => {
    const raw = fs.readFileSync(path.join(tendersDir, f), 'utf-8');
    return JSON.parse(raw) as Tender;
  }).filter(t => t.review_status === 'published');

  // Calculate days remaining
  const today = new Date();
  tenders.forEach(t => {
    if (t.closing_date) {
      const closing = new Date(t.closing_date);
      t.days_remaining = Math.ceil((closing.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
      t.is_active = t.days_remaining > 0;
      t.status = t.days_remaining > 7 ? 'open' : t.days_remaining > 0 ? 'closing_soon' : 'closed';
    }
  });

  // Sort: active first (by closing date asc), then closed
  tenders.sort((a, b) => {
    if (a.is_active && !b.is_active) return -1;
    if (!a.is_active && b.is_active) return 1;
    if (a.is_active && b.is_active) {
      return new Date(a.closing_date).getTime() - new Date(b.closing_date).getTime();
    }
    return new Date(b.closing_date).getTime() - new Date(a.closing_date).getTime();
  });

  _tenderCache = tenders;
  return tenders;
}

export function getActiveTenders(): Tender[] {
  return getAllTenders().filter(t => t.is_active);
}

export function getTenderBySlug(slug: string): Tender | undefined {
  return getAllTenders().find(t => t.slug === slug);
}

export function getTendersByCategory(category: string): Tender[] {
  return getAllTenders().filter(t => t.category === category);
}

export function getTendersBySector(sector: string): Tender[] {
  return getAllTenders().filter(t => t.sectors?.includes(sector));
}

export function getTendersByEntity(entitySlug: string): Tender[] {
  return getAllTenders().filter(t => t.procuring_entity_slug === entitySlug);
}

export function getTendersBySource(source: string): Tender[] {
  return getAllTenders().filter(t => t.source === source);
}

export function getTendersByRegion(region: string): Tender[] {
  return getAllTenders().filter(t => t.region?.toLowerCase() === region.toLowerCase());
}

export function getCategories(): Category[] {
  if (_categoryCache) return _categoryCache;

  if (!fs.existsSync(categoriesDir)) return getDefaultCategories();

  const files = fs.readdirSync(categoriesDir).filter(f => f.endsWith('.json'));
  if (files.length === 0) return getDefaultCategories();

  const categories = files.map(f => {
    const raw = fs.readFileSync(path.join(categoriesDir, f), 'utf-8');
    return JSON.parse(raw) as Category;
  });

  // Add counts
  const allTenders = getAllTenders();
  categories.forEach(cat => {
    cat.count = allTenders.filter(t => t.category === cat.slug).length;
  });

  _categoryCache = categories;
  return categories;
}

function getDefaultCategories(): Category[] {
  return [
    { name: 'Goods & Supplies', slug: 'goods', description: 'Equipment, materials, office supplies, vehicles, and other physical goods', icon: '📦' },
    { name: 'Construction & Works', slug: 'works', description: 'Building, road construction, renovation, and infrastructure projects', icon: '🏗️' },
    { name: 'Consulting Services', slug: 'consulting', description: 'Advisory, research, management consulting, and technical assistance', icon: '💼' },
    { name: 'IT & Technology', slug: 'technology', description: 'Software, hardware, networking, digital transformation projects', icon: '💻' },
    { name: 'General Services', slug: 'services', description: 'Cleaning, security, catering, transport, and other operational services', icon: '🔧' },
    { name: 'Health & Medical', slug: 'health', description: 'Medical supplies, equipment, pharmaceuticals, and healthcare services', icon: '🏥' },
    { name: 'Agriculture', slug: 'agriculture', description: 'Farming inputs, irrigation, agricultural machinery and services', icon: '🌾' },
    { name: 'Education & Training', slug: 'education', description: 'Training programs, educational materials, and institutional development', icon: '📚' },
    { name: 'Energy & Water', slug: 'energy', description: 'Power generation, water supply, solar, renewable energy projects', icon: '⚡' },
    { name: 'Transport & Logistics', slug: 'transport', description: 'Vehicle procurement, freight, logistics, and road maintenance', icon: '🚛' },
  ];
}

export function getUniqueEntities(): { name: string; slug: string; count: number }[] {
  const tenders = getAllTenders();
  const entityMap = new Map<string, { name: string; slug: string; count: number }>();

  tenders.forEach(t => {
    if (t.procuring_entity_slug) {
      const existing = entityMap.get(t.procuring_entity_slug);
      if (existing) {
        existing.count++;
      } else {
        entityMap.set(t.procuring_entity_slug, {
          name: t.procuring_entity,
          slug: t.procuring_entity_slug,
          count: 1,
        });
      }
    }
  });

  return Array.from(entityMap.values()).sort((a, b) => b.count - a.count);
}

export function getUniqueSectors(): { name: string; slug: string; count: number }[] {
  const tenders = getAllTenders();
  const sectorMap = new Map<string, number>();

  tenders.forEach(t => {
    t.sectors?.forEach(s => {
      sectorMap.set(s, (sectorMap.get(s) || 0) + 1);
    });
  });

  return Array.from(sectorMap.entries())
    .map(([slug, count]) => ({
      name: slug.split('-').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' '),
      slug,
      count,
    }))
    .sort((a, b) => b.count - a.count);
}

export function getSources(): { name: string; slug: string; count: number }[] {
  const tenders = getAllTenders();
  const sourceMap = new Map<string, number>();

  tenders.forEach(t => {
    if (t.source) {
      sourceMap.set(t.source, (sourceMap.get(t.source) || 0) + 1);
    }
  });

  const sourceNames: Record<string, string> = {
    ppda: 'PPDA',
    maneps: 'MANEPS',
    eu_ted: 'EU TED',
    world_bank: 'World Bank',
    afdb: 'African Development Bank',
    ungm: 'UN Global Marketplace',
    escom: 'ESCOM',
    mra: 'Malawi Revenue Authority',
    editorial: 'Editorial',
  };

  return Array.from(sourceMap.entries())
    .map(([slug, count]) => ({
      name: sourceNames[slug] || slug.toUpperCase(),
      slug,
      count,
    }))
    .sort((a, b) => b.count - a.count);
}

export interface SourceInfo {
  slug: string;
  name: string;
  fullName: string;
  description: string;
  website: string;
  icon: string;
  about: string;
}

export function getSourceInfo(): SourceInfo[] {
  return [
    {
      slug: 'ppda',
      name: 'PPDA',
      fullName: 'Public Procurement and Disposal of Assets Authority',
      description: 'Browse government tenders published by the Public Procurement and Disposal of Assets Authority (PPDA) of Malawi.',
      website: 'https://www.ppda.mw',
      icon: '🏛️',
      about: 'The PPDA is Malawi\'s central regulatory body for public procurement under the PPDA Act 2025 (Act No. 7 of 2025). It oversees all government purchasing, ensures transparency and value for money, and maintains the register of approved suppliers. All Procuring and Disposing Entities (PDEs) — ministries, departments, statutory corporations, district councils — must follow PPDA guidelines and publish tenders through official channels.',
    },
    {
      slug: 'maneps',
      name: 'MANEPS',
      fullName: 'Malawi National Electronic Procurement System',
      description: 'Find tenders from MANEPS, Malawi\'s new mandatory electronic procurement platform launching April 2026.',
      website: 'https://www.maneps.mw',
      icon: '💻',
      about: 'MANEPS is Malawi\'s national e-procurement system, developed with support from the World Bank under the GGPDP. It became mandatory for all government procurement entities in April 2026. The platform digitises the entire procurement cycle — from tender publication and bid submission to evaluation and contract award. Suppliers must register on MANEPS to participate in government procurement.',
    },
    {
      slug: 'world_bank',
      name: 'World Bank',
      fullName: 'World Bank Group Procurement',
      description: 'World Bank-funded procurement opportunities in Malawi from the Bank\'s active project portfolio.',
      website: 'https://projects.worldbank.org',
      icon: '🌍',
      about: 'The World Bank Group has an active portfolio of over $3.23 billion in Malawi across multiple sectors including education, health, agriculture, energy, and governance. Bank-funded projects follow the World Bank Procurement Regulations (2016, revised 2023), which have their own rules separate from national procurement law. Payments are typically processed within 30-60 days. These tenders are often high-value and open to international bidders.',
    },
    {
      slug: 'eu_ted',
      name: 'EU TED',
      fullName: 'Tenders Electronic Daily — European Union',
      description: 'EU-funded procurement notices for Malawi from the European Union\'s Tenders Electronic Daily (TED) platform.',
      website: 'https://ted.europa.eu',
      icon: '🇪🇺',
      about: 'Tenders Electronic Daily (TED) is the official journal for European Union public procurement. The EU has committed EUR 352 million to Malawi for the 2021-2027 programming period under the Neighbourhood, Development and International Cooperation Instrument (NDICI). EU-funded tenders in Malawi cover governance, agriculture, climate resilience, and economic development. These opportunities follow EU procurement procedures and are typically high-value contracts.',
    },
    {
      slug: 'ungm',
      name: 'UN Procurement',
      fullName: 'United Nations Global Marketplace',
      description: 'Procurement opportunities from United Nations agencies operating in Malawi via the UN Global Marketplace (UNGM).',
      website: 'https://www.ungm.org',
      icon: '🇺🇳',
      about: 'The UN Global Marketplace (UNGM) is the common procurement portal for all UN agencies, funds, and programmes. In Malawi, active UN agencies include UNDP, UNICEF, WFP, UNFPA, WHO, FAO, and UN Women. UN procurement in Malawi covers humanitarian assistance, development programmes, health supplies, food security, and capacity building. Suppliers must register on UNGM and may need to meet specific UN vendor requirements.',
    },
    {
      slug: 'escom',
      name: 'ESCOM',
      fullName: 'Electricity Supply Corporation of Malawi',
      description: 'Procurement notices from ESCOM for power infrastructure, equipment, and services across Malawi.',
      website: 'https://www.escom.mw',
      icon: '⚡',
      about: 'The Electricity Supply Corporation of Malawi (ESCOM) is the sole electricity distributor in the country, responsible for transmission and distribution of power to over 1.5 million customers. ESCOM procures equipment (transformers, cables, meters), construction services (substations, power lines), and professional services. Tenders are published on the ESCOM website and typically require PPDA-registered suppliers.',
    },
    {
      slug: 'mra',
      name: 'MRA',
      fullName: 'Malawi Revenue Authority',
      description: 'Procurement opportunities from the Malawi Revenue Authority for IT systems, office supplies, and services.',
      website: 'https://www.mra.mw',
      icon: '🏦',
      about: 'The Malawi Revenue Authority (MRA) is the government agency responsible for collecting taxes and customs duties. MRA is one of Malawi\'s largest public sector procurers, regularly issuing tenders for IT systems, office equipment, fleet vehicles, security services, and professional consultancies. MRA follows PPDA procurement guidelines and publishes tenders on its website.',
    },
  ];
}

export function formatDate(dateStr: string): string {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

export function formatCurrency(amount: number | null, currency: string = 'MWK'): string {
  if (amount === null || amount === undefined) return 'Not disclosed';
  return new Intl.NumberFormat('en-MW', { style: 'currency', currency, maximumFractionDigits: 0 }).format(amount);
}
