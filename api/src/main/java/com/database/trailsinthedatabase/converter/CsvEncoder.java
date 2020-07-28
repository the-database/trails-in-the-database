package com.database.trailsinthedatabase.converter;

import com.fasterxml.jackson.core.JsonGenerator;
import com.fasterxml.jackson.core.util.ByteArrayBuilder;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.ObjectWriter;
import com.fasterxml.jackson.databind.SequenceWriter;
import com.fasterxml.jackson.dataformat.csv.CsvMapper;
import com.fasterxml.jackson.dataformat.csv.CsvSchema;
import org.reactivestreams.Publisher;
import org.springframework.core.ResolvableType;
import org.springframework.core.codec.Encoder;
import org.springframework.core.io.buffer.DataBuffer;
import org.springframework.core.io.buffer.DataBufferFactory;
import org.springframework.http.MediaType;
import org.springframework.util.MimeType;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

import java.io.IOException;
import java.util.*;

public class CsvEncoder<T> implements Encoder<T> {

    public static final String CSV_MIME_TYPE_VALUE = "text/csv";
    public static final MimeType CSV_MIME_TYPE = new MediaType("text", "csv");

    private static final List<MimeType> CSV_MIME_TYPES = List.of(CSV_MIME_TYPE);

    private final ObjectMapper jsonMapper;

    public CsvEncoder(ObjectMapper jsonObjectMapper) {
        this.jsonMapper = jsonObjectMapper;
    }

    @Override
    public boolean canEncode(ResolvableType elementType, MimeType mimeType) {
        if (mimeType == null) {
            return true;
        }
        return CSV_MIME_TYPES.stream().anyMatch(m -> m.isCompatibleWith(mimeType));
    }

    @Override
    public Flux<DataBuffer> encode(Publisher<? extends T> inputStream, DataBufferFactory bufferFactory, ResolvableType elementType, MimeType mimeType, Map<String, Object> hints) {

        Flux<? extends T> array = Flux.from(inputStream);

        Flux<DataBuffer> result = array.next().flatMap(value -> Mono.just(getCsvWriter(value))).flatMapMany(objectWriter -> {
            try {
                ByteArrayBuilder byteArrayBuilder = new ByteArrayBuilder(objectWriter.getFactory()._getBufferRecycler());
                JsonGenerator generator = objectWriter.getFactory().createGenerator(byteArrayBuilder);
                SequenceWriter sequenceWriter = objectWriter.writeValues(generator);

                return array.map(value ->
                    encodeStreamingValue(value, bufferFactory, hints, sequenceWriter, byteArrayBuilder)
                );
            } catch (IOException e) {
                e.printStackTrace();
            }

            return Flux.empty();
        });

        return result;
    }

    private DataBuffer encodeStreamingValue(Object value, DataBufferFactory dataBufferFactory, Map<String, Object> hints,
                                            SequenceWriter sequenceWriter, ByteArrayBuilder byteArrayBuilder) {
        try {
            sequenceWriter.write(value);
            sequenceWriter.flush();
            byte[] bytes = byteArrayBuilder.toByteArray();
            byteArrayBuilder.reset();

            int offset = 0;
            int length = bytes.length;

            DataBuffer buffer = dataBufferFactory.allocateBuffer(length);
            buffer.write(bytes, offset, length);

            return buffer;
        } catch (IOException e) {
            e.printStackTrace();
        }
        return null;
    }

    @Override
    public List<MimeType> getEncodableMimeTypes() {
        return CSV_MIME_TYPES;
    }

    private ObjectWriter getCsvWriter(T object) {
        Set<String> fields = getUniqueFieldNames(object);
        CsvSchema.Builder schemaBuilder = CsvSchema.builder().setUseHeader(true);
        for (String field : fields) {
            schemaBuilder.addColumn(field);
        }
        return new CsvMapper().writerFor(object.getClass()).with(schemaBuilder.build());
    }

    private Set<String> getUniqueFieldNames(T object) {
        try {
            JsonNode root = jsonMapper.readTree(jsonMapper.writeValueAsString(object));
            Set<String> uniqueFieldNames = new LinkedHashSet<>();
            Iterator<String> it = root.fieldNames();
            while (it.hasNext()) {
                String field = it.next();
                uniqueFieldNames.add(field);
            }
            return uniqueFieldNames;
        } catch (IOException ex) {
            throw new RuntimeException(ex);
        }
    }
}
