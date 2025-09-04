from dataclasses import dataclass, field, asdict
from typing import List, Any, Optional
from datetime import datetime


@dataclass
class MessageData:
    msg_id: str
    role: str
    content: Any
    timestamp: datetime

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ThreadData:
    _id: str
    user_id: str
    function_name: str
    title: Optional[str] = None
    messages: List[MessageData] = field(default_factory=list)
    long_term_memory: List[Any] = field(default_factory=list)
    vectorestore: str = None
    create_timestamp: datetime = field(default_factory=datetime.now)
    last_timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        data = asdict(self)
        data['messages'] = [m.to_dict() for m in self.messages]
        return data