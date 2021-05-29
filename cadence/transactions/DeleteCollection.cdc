import AMProject from 0x5cc83cb6d766bf4a

// This transaction allows the Minter account to mint an NFT
// and deposit it into its collection.

transaction() {

    // let myProject: @AMProject.Project
    // let collectionRef: &AMProject.Collection

    prepare(acct: AuthAccount) {
        let collectionResource <- acct.load<@AMProject.Collection>(from: /storage/AMProjects)
        destroy collectionResource
    }

    execute {
        
    }
}