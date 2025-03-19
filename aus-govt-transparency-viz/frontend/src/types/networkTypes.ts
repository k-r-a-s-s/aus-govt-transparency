/**
 * Node in a network graph
 */
export interface Node {
  id: string;
  name: string;
  type: 'mp' | 'entity';
  party?: string;
  count?: number;
  x?: number;
  y?: number;
  fx?: number | null;
  fy?: number | null;
}

/**
 * Link between nodes in a network graph
 */
export interface Link {
  source: string | Node;
  target: string | Node;
  value: number;
  type: string;
}

/**
 * Complete MP network data for visualization
 */
export interface MPNetworkData {
  nodes: Node[];
  links: Link[];
}

/**
 * Entity connection data
 */
export interface EntityConnection {
  entity: string;
  mp_name: string;
  relationship_type: string;
  value: string;
  date_logged: string;
  party?: string;
}

/**
 * MP connection data
 */
export interface MPConnection {
  mp_name: string;
  party: string;
  connections: EntityConnection[];
} 