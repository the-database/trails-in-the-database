CREATE TABLE game (
  id int primary key,
  title_eng text NOT NULL,
  title_jpn_roman text NOT NULL,
  title_jpn text NOT NULL
);

INSERT INTO game VALUES (1,'Trails in the Sky','Sora no Kiseki FC','空の軌跡FC'),(2,'Trails in the Sky SC','Sora no Kiseki SC','空の軌跡SC'),(3,'Trails in the Sky the 3rd','Sora no Kiseki the 3rd','空の軌跡 the 3rd'),(4,'Trails from Zero','Zero no Kiseki','零の軌跡'),(5,'Trails to Azure','Ao no Kiseki','碧の軌跡'),(6,'Trails of Cold Steel','Sen no Kiseki','閃の軌跡'),(7,'Trails of Cold Steel II','Sen no Kiseki II','閃の軌跡II'),(8,'Trails of Cold Steel III','Sen no Kiseki III','閃の軌跡III'),(9,'Trails of Cold Steel IV','Sen no Kiseki IV','閃の軌跡IV');
