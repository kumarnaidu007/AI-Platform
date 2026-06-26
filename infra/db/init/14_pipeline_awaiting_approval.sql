-- Pipeline can pause for human approval after planning phase
ALTER TYPE pipeline_status ADD VALUE IF NOT EXISTS 'awaiting_approval';
