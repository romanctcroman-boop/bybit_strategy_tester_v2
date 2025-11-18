export type Tool =
  | 'select'
  | 'trendline'
  | 'ray'
  | 'hline'
  | 'hray'
  | 'vline'
  | 'fib'
  | 'rect'
  | 'channel'
  | 'ruler';

export type Point = {
  time: number; // seconds since epoch (UTCTimestamp like in series data)
  price: number;
};

export type Shape =
  | {
      id: string;
      type: 'trendline';
      p1: Point;
      p2: Point;
    }
  | {
      id: string;
      type: 'ray';
      p1: Point; // start
      p2: Point; // direction
    }
  | {
      id: string;
      type: 'hline';
      price: number;
    }
  | {
      id: string;
      type: 'hray';
      p: Point; // start point (timeStart, price)
    }
  | {
      id: string;
      type: 'vline';
      time: number;
    }
  | {
      id: string;
      type: 'fib';
      p1: Point; // anchor A
      p2: Point; // anchor B
      levels?: number[]; // optional custom levels, default common set
    }
  | {
      id: string;
      type: 'rect';
      p1: Point; // corner A
      p2: Point; // opposite corner B
    }
  | {
      id: string;
      type: 'channel';
      p1: Point; // line start
      p2: Point; // line end
      widthPx: number; // parallel offset in pixels
    }
  | {
      id: string;
      type: 'ruler';
      p1: Point;
      p2: Point;
    };

export type Theme = {
  stroke: string;
  strokeActive: string;
  bg?: string;
};
