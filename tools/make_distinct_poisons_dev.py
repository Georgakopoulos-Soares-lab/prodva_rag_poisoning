#!/usr/bin/env python
"""Hand-crafted, distinctness-constrained EVAL poisons: template-matched Mol-Instructions
style but the biology genuinely reworded (paraphrased, no verbatim reaction strings)."""
import json, re, hashlib, pathlib, statistics as st
ROOT = pathlib.Path("/scratch/10899/kimopro/prodva_rag_poison")

DISTINCT = {
"MI-TEST-04082":"Generate a protein sequence optimized for the following function requirements. 1. The protein should act in the cytoplasm during oxidative and genotoxic stress as an anti-sigma-factor antagonist. 2. It should shield the stationary-phase stress sigma subunit from turnover by interfering with its RssB-directed degradation, raising that sigma factor's abundance.",
"MI-TEST-03421":"Create a protein sequence that satisfies the following specifications: 1. The protein should coordinate calcium and zinc ions and cleave ceramide-class sphingolipids into a free fatty acid plus a long-chain sphingoid base. 2. It should drive sphingoid-base production and sphingolipid turnover and modulate inflammatory signaling and cell proliferation.",
"MI-TEST-00791":"Design a protein sequence that is tailored to the desired application. 1. The protein should consume ATP to refold denatured polypeptides, gripping unfolded chains tightly. 2. It should sit at the host-cell interface and cytoplasm and help a symbiont evade macrophage killing while promoting host entry.",
"MI-TEST-01179":"Design a functional protein sequence with the following characteristics: 1. The fold should alternate beta strands and alpha helices. 2. The protein should associate with RNA and sever nucleic-acid phosphodiester bonds.",
"MI-TEST-05823":"Synthesize a protein sequence with the appropriate folding and stability properties for the desired function. 1. The protein should spend ATP to attach meso-diaminopimelate onto a UDP-linked muramoyl-peptide precursor during peptidoglycan construction. 2. It should adopt a Mur-family ligase core and support cell-wall building and division.",
"MI-TEST-02466":"Generate a protein sequence that meets the functional requirements while minimizing unwanted side effects. 1. The protein should traverse the inner membrane through long helical segments and shuttle an iron-siderophore complex across it. 2. It should import the ferric form of the anguibactin carrier and keep cellular iron balanced.",
"MI-TEST-02579":"Develop a protein sequence with increased stability under specific condition. 1. With S-adenosylmethionine as methyl donor, the protein should deposit two methyl groups on one guanosine (position 26) of many transfer RNAs. 2. It should recognize tRNA broadly and adopt a Trm1-type methyltransferase fold.",
"MI-TEST-03779":"Synthesize a protein sequence that satisfies the given functional constraints. 1. The protein should work in the cytoplasm and adjust flux through the de-novo methionine-building route. 2. It should fold as an alpha/beta-hydrolase.",
"MI-TEST-05853":"Create a protein sequence with the necessary features to perform the desired function. 1. The protein should interconvert lactate and pyruvate with an NAD cofactor. 2. It should back fermentative lactate output and glycolysis, holding NAD and substrate firmly.",
"MI-TEST-01737":"Create a protein sequence that satisfies the following specifications: 1. The protein should carry a [4Fe-4S] cluster and interconvert two isopropylmalate isomers through a dehydrated intermediate. 2. It should serve the leucine-building pathway and recognize that route's intermediates.",
"MI-TEST-03331":"Design a protein sequence that exhibits the desired activity and specificity. 1. The protein should up-regulate the MAP-kinase cascade triggered by mating pheromone. 2. It should help produce the secreted M-factor mating signal.",
"MI-TEST-03058":"Generate a protein sequence optimized for the following function requirements. 1. The protein should help assemble the multi-subunit RNA polymerase by clamping the ends of its largest subunit together. 2. It should support template-guided extension of an RNA chain from ribonucleotide triphosphates.",
"MI-TEST-04864":"Design a protein sequence that is tailored to the desired application. 1. The protein should recognize mannose, chitin and N-acetylglucosamine sugar chains in a calcium-dependent manner. 2. It should behave as a carbohydrate-binding lectin sensing microbial surface glycans.",
"MI-TEST-00325":"Construct a protein sequence with the desired structural and functional characteristics. 1. The protein should copy RNA templates into new RNA to replicate and transcribe a segmented viral genome. 2. It should bind the viral promoter and grab caps from host messages through an endonuclease step, using an RNA-directed-polymerase core.",
"MI-TEST-01032":"Create a protein sequence that satisfies the following specifications: 1. The active center should hold both an acidic and a basic residue positioned for stable acid-base catalysis.",
"MI-TEST-02373":"Synthesize a protein sequence that has the desired solubility or other physical properties for the intended use. 1. The protein should move sugar groups onto acceptor molecules, acting as a sugar-transferring enzyme.",
"MI-TEST-04396":"Design a protein sequence that exhibits the desired activity and specificity. 1. The protein should methylate one adenine (at C2) inside ribosomal RNA. 2. It should bind a metal ion and a [4Fe-4S] cluster to modify rRNA bases.",
"MI-TEST-03317":"Synthesize a protein sequence with the appropriate folding and stability properties for the desired function. 1. The protein should run two back-to-back steps of the non-mevalonate isoprenoid route, first joining CTP to methylerythritol phosphate and later closing a cyclic diphosphate with release of CMP. 2. It should bind a metal ion and feed terpenoid precursor supply.",
"MI-TEST-05625":"Synthesize a protein sequence that has the desired solubility or other physical properties for the intended use. 1. The protein should be a nuclear assembly chaperone that helps build the base of the proteasome's 19S regulatory particle. 2. It may also aid DNA mismatch repair in slowly dividing cells.",
"MI-TEST-05254":"Design a functional protein sequence with the following characteristics: 1. The protein should shuttle a phosphate between adenine nucleotides, yielding ATP and AMP from two ADP molecules.",
"MI-TEST-02573":"Develop a protein sequence with increased stability under specific condition. 1. The protein should be a class-I viral fusion protein that merges the virion envelope with the host endosomal membrane on entry. 2. It should bear a signal peptide, a membrane anchor and a YXXL trafficking motif, resembling a retroviral envelope fusion subunit.",
"MI-TEST-04241":"Synthesize a protein sequence that has the desired solubility or other physical properties for the intended use. 1. The protein should carry an NAD-binding semialdehyde-dehydrogenase fold and form dimers. 2. It should act early in the aspartate-to-threonine route using a conserved proton-accepting residue.",
"MI-TEST-04526":"Develop a protein sequence with increased stability under specific condition. 1. The protein should trim terminal beta-linked galactose from glycoconjugates such as gangliosides, glycoproteins and glycosaminoglycans. 2. It should carry a signal peptide and act in the vacuole or outside the cell during sugar-polymer breakdown.",
"MI-TEST-00264":"Synthesize a protein sequence that has the desired solubility or other physical properties for the intended use. 1. The protein should chaperone RNA, binding small regulatory RNAs, messenger RNAs and tRNAs in the cytosol. 2. It should adopt an Sm fold and tune transcript stability and translation under stress.",
"MI-TEST-01809":"Construct a protein sequence with the desired structural and functional characteristics. 1. The protein should be secreted and carry out its role outside the cell.",
"MI-TEST-05267":"Generate a protein sequence optimized for the following function requirements. 1. The protein should relay a phosphate through a histidine intermediate to make triphosphate nucleotides other than ATP. 2. It should bind ATP and a metal ion at a conserved phospho-histidine site.",
"MI-TEST-02553":"Generate a protein sequence that meets the functional requirements while minimizing unwanted side effects. 1. The protein should carry a reticulon domain and helical membrane-spanning segments that curve the tubular endoplasmic reticulum. 2. It should bind a ubiquitin ligase and influence cell migration and sphingolipid balance.",
"MI-TEST-02031":"Design a protein sequence that is tailored to the desired application. 1. The protein should take part in pre-messenger-RNA splicing within U2-type spliceosomal assemblies and the Prp19 complex. 2. It should be rich in polar and charged residues.",
"MI-TEST-00043":"Create a protein sequence that satisfies the following specifications: 1. The protein should break down other proteins by hydrolyzing peptide bonds, driving cellular protein turnover.",
"MI-TEST-03894":"Synthesize a protein sequence that satisfies the given functional constraints. 1. The protein should bind ATP with high specificity.",
}

payload = json.load(open(ROOT/"artifacts/attack/payload.json"))
targets = {json.loads(l)["target_id"]: json.loads(l) for l in open(ROOT/"artifacts/attack/targets_eval.jsonl")}
def cw(s): return set(w for w in re.findall(r"[a-z0-9]+", s.lower()) if len(w)>3)
BOILER = cw("develop design create generate synthesize construct protein sequence designed engineered should must able perform function functional characteristics following specific specifications desired activity properties condition intended requirements features include contain provide within order")
out = ROOT/"artifacts/attack/poison_records_eval_distinct.jsonl"
jall=[]; jfn=[]
with open(out,"w") as f:
    for k,tid in enumerate(targets):
        desc=DISTINCT[tid]
        f.write(json.dumps({"poison_id":f"P-EVALD-{k:03d}","target_id":tid,"description":desc,
            "description_sha256":hashlib.sha256(desc.encode()).hexdigest(),
            "payload_name":payload["payload_name"]})+"\n")
        tw=cw(targets[tid]["prompt"]); pw=cw(desc)
        jall.append(len(tw&pw)/len(tw|pw))
        tf=tw-BOILER; pf=pw-BOILER
        jfn.append(len(tf&pf)/len(tf|pf) if (tf|pf) else 0)
print(f"wrote {out} ({len(DISTINCT)} distinct poisons)")
print(f"content-word Jaccard (all)      : median={st.median(jall):.2f} min={min(jall):.2f} max={max(jall):.2f}")
print(f"content-word Jaccard (function) : median={st.median(jfn):.2f} min={min(jfn):.2f} max={max(jfn):.2f}")
print(f"n with function-Jaccard > 0.5   : {sum(1 for j in jfn if j>0.5)}/{len(jfn)}")
