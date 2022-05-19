from sqlalchemy import create_engine, ForeignKey, Table
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import Column, Integer, String, Date, Boolean, Float
from sqlalchemy.orm import sessionmaker


engine = create_engine('sqlite:///data/records3.db', echo=False)
Base = declarative_base()


class Url(Base):
    __tablename__ = 'urls'
    id = Column(Integer, primary_key=True)
    url = Column(String, unique=True)
    processed = Column(Boolean, default=False)

    def __init__(self, url, processed=False):
        if not url.startswith('http'):
            url = f'https://hemnet.se{url}'
        self.url = url
        self.processed = processed

    def __hash__(self):
        return hash(self.url)

    def __eq__(self, __o: object) -> bool:
        return self.url == __o.url

    @staticmethod
    def all_urls():
        return set(db.query(Url).all())

    @staticmethod
    def all_unprocessed_urls():
        return set(db.query(Url).filter(Url.processed == False).all())


building_location = Table('building_location', Base.metadata,
    Column('location_id', ForeignKey('location_tags.id')),
    Column('building_id', ForeignKey('buildings.id'))
)


class LocationTag(Base):
    __tablename__ = 'location_tags'
    id = Column(Integer, primary_key=True, autoincrement=True)
    tag = Column(String(length=30))

    buildings = relationship('Building', secondary=building_location, back_populates='location_tags')

    def __eq__(self, other):
        return self.tag == other.tag

    @property
    def existing(self):
        return db.query(LocationTag).filter(LocationTag.tag == self.tag).first()


class Building(Base):
    __tablename__ = 'buildings'
    id = Column(Integer, primary_key=True)
    address = Column(String)
    built = Column(Date, nullable=True)
    total_floors = Column(Integer, nullable=True)
    has_lift = Column(Boolean, nullable=True, default=False)
    map_url = Column(String, nullable=True)
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)
    apartments = relationship('Apartment', back_populates='building')


    location_tags = relationship('LocationTag', secondary=building_location, back_populates='buildings')

    @staticmethod
    def from_json(js):
        kwargs = {}
        allowed_kwargs = [n.name for n in Building.__table__.columns._all_columns]
        if js.get('id'):
            del js['id']
        for key, value in js.items():
            if key in allowed_kwargs:
                kwargs[key] = value
        return Building(**kwargs)

    @property
    def existing(self):
        return db.query(Building).filter(Building.address == self.address).first()

    def add_tags(self, tags):
        new = [LocationTag(tag=t) for t in tags]
        new = [t.existing or t for t in new]
        for tag in new:
            if tag not in self.location_tags:
                self.location_tags.append(tag)
            else:
                pass  # print('tag already exists')


class Apartment(Base):
    __tablename__ = 'apartments'
    id = Column(Integer, primary_key=True, autoincrement=True)
    property_type = Column(String, nullable=True)  # E.g Bostadsrättlägenhet
    rooms = Column(Integer, nullable=True)
    living_space = Column(Integer, nullable=True)
    has_balcony = Column(Boolean, nullable=True)  # Null means don't know (probably False)
    floor = Column(Integer, nullable=True)
    avgift = Column(Integer, nullable=True)
    driftskostnad = Column(Integer, nullable=True)
    sales = relationship('Sale', back_populates='apartment')

    building_id = Column(Integer, ForeignKey('buildings.id'))
    building = relationship('Building', back_populates='apartments')


    @staticmethod
    def from_json(js):
        kwargs = {}
        allowed_kwargs = [n.name for n in Apartment.__table__.columns._all_columns]
        if js.get('id'):
            del js['id']
        for key, value in js.items():
            if key in allowed_kwargs:
                kwargs[key] = value

        return Apartment(**kwargs)

    def __eq__(self, other):
        # Not perfectly reliable but a reasonable guess
        return self.building_id == other.building_id \
               and self.rooms == other.rooms \
               and self.living_space == other.living_space \
               and self.floor == other.floor \
               and self.has_balcony == other.has_balcony

    @property
    def existing(self):
        ret = db.query(Apartment)\
            .filter(Apartment.building == self.building)\
            .filter(Apartment.rooms == self.rooms)\
            .filter(Apartment.living_space == self.living_space)\
            .filter(Apartment.floor == self.floor)\
            .filter(Apartment.has_balcony == self.has_balcony)\
            .first()
        return ret


class Sale(Base):
    __tablename__ = 'sales'
    id = Column(Integer, primary_key=True)
    sale_date = Column(Date)
    asked_price = Column(Integer, nullable=True)
    sold_price = Column(Integer)

    apartment = relationship('Apartment')
    apartment_id =Column(Integer, ForeignKey('apartments.id'))

    url_id = Column(Integer, ForeignKey('urls.id'))
    url = relationship('Url')

    @staticmethod
    def from_json(js):
        kwargs = {}
        allowed_kwargs = [n.name for n in Sale.__table__.columns._all_columns]
        for key, value in js.items():
            if key in allowed_kwargs:
                kwargs[key] = value

        return Sale(**kwargs)


Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
db = Session()
